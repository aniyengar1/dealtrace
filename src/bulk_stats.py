"""Headline stats across canonical deals (deals.is_canonical, after
src.dedup_deals has run -- both curated and bulk-discovered rows,
whichever one is each transaction's canonical representative).

    python -m src.bulk_stats

Mirrors the established conventions in apps/web/src/lib/dealSummary.ts
(nBidders, firstBidProposal/finalBidProposal via price_high ?? price_low
and accepted-else-last-dated, daysFirstContactToSigning via
first_contact-else-earliest-date to latest signing) rather than
inventing new definitions, except where this task's own spec is
explicitly narrower (percent-increase is restricted to cash deals with
both prices, which dealSummary.ts's pctChange does not do) or adds
data-quality filtering dealSummary.ts doesn't need (that code runs over
hand-curated, reviewed deals; this runs over ~1000 unreviewed
extractions, where a stray near-zero first price or a misdated event
can produce a nonsense outlier -- see the thresholds below).

Target-side placeholder terms ("the Company", "Target", "Board", etc.)
are resolved to each deal's own target name before any proposer/
recipient comparison via src.entity_match.is_same_entity, not exact
string equality -- extracted text uses informal short names ("Knoll")
that never exactly match EDGAR's raw legal name ("KNOLL INC").

Per-deal compute_*_for_deal functions are the single source of truth
for both this module's aggregate stats AND src.deal_metrics's
per-deal row -- a deal's exclusion reason (and often its raw computed
value, even when excluded) is returned alongside the value so
deal_metrics can store exactly what each aggregate used or skipped,
instead of recomputing a second, possibly-drifting copy of the same
logic. When this module runs standalone it also refreshes both DB
metrics tables (src.deal_metrics.refresh_all) and the JSON file.
"""

import json
import statistics
from datetime import date
from pathlib import Path
from typing import Optional

import psycopg

from src import validate
from src.entity_match import is_acronym_of, is_same_entity
from src.env import load_env
from src.load_db import connect

load_env()

PROMPT_LOCK_PATH = Path("config/prompt_lock.json")

CONTACT_EVENT_TYPES = {"first_contact", "nda", "discussion"}
N_OUTLIERS = 10

# Data-quality thresholds for the two stats most exposed to a single bad
# extracted number (a near-zero first price, or a misdated event).
# Excluded deals are listed by reason, never silently dropped.
MIN_FIRST_PRICE_USD = 0.10
MIN_FIRST_PRICE_PCT_OF_FINAL = 0.05
MAX_ABS_PCT_CHANGE = 300.0
MAX_DAYS_FOR_REVIEW = 2000
REVIEW_PCT_DROP_THRESHOLD = -90.0


def _resolve_target(name: Optional[str], target: str) -> Optional[str]:
    if name and (
        name.strip().lower() in validate._TARGET_DEFINED_TERMS
        or is_same_entity(name, target)
        or is_acronym_of(name, target)
    ):
        return target
    return name


def _load_prompt_lock_run_dirs() -> dict[str, str]:
    if not PROMPT_LOCK_PATH.exists():
        return {}
    data = json.loads(PROMPT_LOCK_PATH.read_text())
    return {slug: info["run_dir"] for slug, info in data.get("results", {}).items()}


_PROMPT_LOCK_RUN_DIRS = _load_prompt_lock_run_dirs()


def _resolve_run_id_for_deal(conn: psycopg.Connection, deal_id: str, slug: str) -> Optional[str]:
    """Exactly one extraction_runs row per deal, never a sum across
    several -- a curated deal that went through the v8-v12 prompt
    iteration cycle (Splunk, Zendesk) has one extraction_runs row PER
    ITERATION, and joining on deal_id alone (the previous behavior)
    silently summed proposals/events across all of them, inflating
    every count (Splunk showed 43 proposals across 3 runs instead of
    the locked v11 run's real 14). config/prompt_lock.json's own
    run_dir is authoritative when present (it can name an OLDER run
    than the globally "locked_prompt_version" -- e.g. Splunk's locked
    run is explicitly v11, not v12, because v12 only added unrelated
    functionality and v11's validated result stands). Otherwise falls
    back to the most recently started run, which is a no-op for the
    ~1123 deals that only ever had exactly one run anyway."""
    if slug in _PROMPT_LOCK_RUN_DIRS:
        row = conn.execute(
            "SELECT id FROM extraction_runs WHERE deal_id = %s AND run_dir = %s",
            (deal_id, _PROMPT_LOCK_RUN_DIRS[slug]),
        ).fetchone()
        if row:
            return row[0]
    row = conn.execute(
        "SELECT id FROM extraction_runs WHERE deal_id = %s ORDER BY started_at DESC LIMIT 1",
        (deal_id,),
    ).fetchone()
    return row[0] if row else None


def _fetch_canonical_deals(conn: psycopg.Connection) -> list[dict]:
    return fetch_deals(conn, canonical_only=True)


def fetch_deals(conn: psycopg.Connection, canonical_only: bool = False) -> list[dict]:
    """Like _fetch_canonical_deals, but canonical_only=False also
    returns non-canonical deals (deal_id included) -- src.deal_metrics
    needs a row for every deal, not just the canonical ones used in
    aggregates."""
    query = "SELECT d.id, d.slug, d.deal_name, d.target, d.acquirer FROM deals d"
    if canonical_only:
        query += " WHERE d.is_canonical"
    rows = conn.execute(query).fetchall()
    deals = []
    for deal_id, slug, deal_name, target, acquirer in rows:
        run_id = _resolve_run_id_for_deal(conn, deal_id, slug)
        if run_id is None:
            events, proposals = [], []
        else:
            events = conn.execute(
                """
                SELECT e.date_start, e.event_type, e.parties
                FROM events e
                WHERE e.run_id = %s AND e.passed
                """,
                (run_id,),
            ).fetchall()
            proposals = conn.execute(
                """
                SELECT p.date_resolved, p.proposer, p.recipient, p.price_low, p.price_high,
                       p.consideration_type, p.status
                FROM proposals p
                WHERE p.run_id = %s AND p.passed
                """,
                (run_id,),
            ).fetchall()
        deals.append(
            {
                "deal_id": deal_id,
                "slug": slug,
                "deal_name": deal_name,
                "target": target,
                "acquirer": acquirer,
                "events": [
                    {
                        "date_start": e[0],
                        "event_type": e[1],
                        "parties": [_resolve_target(p, target) for p in (e[2] or [])],
                    }
                    for e in events
                ],
                "proposals": [
                    {
                        "date_resolved": p[0],
                        "proposer": _resolve_target(p[1], target),
                        "recipient": _resolve_target(p[2], target),
                        "price_low": float(p[3]) if p[3] is not None else None,
                        "price_high": float(p[4]) if p[4] is not None else None,
                        "consideration_type": p[5],
                        "status": p[6],
                    }
                    for p in proposals
                ],
            }
        )
    return deals


def _dated_proposals(proposals: list[dict]) -> list[dict]:
    dated = [p for p in proposals if p["date_resolved"] is not None]
    dated.sort(key=lambda p: p["date_resolved"])
    return dated


def _price(p: dict) -> Optional[float]:
    return p["price_high"] if p["price_high"] is not None else p["price_low"]


def _final_entry(dated: list[dict]) -> Optional[dict]:
    accepted = [p for p in dated if p["status"] == "accepted"]
    if accepted:
        return accepted[-1]
    return dated[-1] if dated else None


def _distribution(values: list[float]) -> dict:
    if not values:
        return {"min": None, "p25": None, "median": None, "p75": None, "max": None}
    sorted_values = sorted(values)
    if len(values) >= 4:
        q1, _, q3 = statistics.quantiles(sorted_values, n=4, method="inclusive")
    else:
        q1 = q3 = statistics.median(sorted_values)
    return {
        "min": sorted_values[0],
        "p25": q1,
        "median": statistics.median(sorted_values),
        "p75": q3,
        "max": sorted_values[-1],
    }


# --- per-deal computations (shared with src.deal_metrics) --------------------


def compute_n_parties_contacted_for_deal(d: dict) -> int:
    contacted = {
        name
        for e in d["events"]
        if e["event_type"] in CONTACT_EVENT_TYPES
        for name in e["parties"]
        if name and name != d["target"]
    }
    return len(contacted)


def compute_n_bidders_for_deal(d: dict) -> int:
    return len({p["proposer"] for p in d["proposals"] if p["proposer"] and p["proposer"] != d["target"]})


def compute_n_proposals_for_deal(d: dict) -> int:
    return len(d["proposals"])


def compute_first_final_price_for_deal(d: dict) -> tuple[Optional[float], Optional[float]]:
    """First dated proposal's price and the final (accepted, else
    latest-dated) proposal's price -- independent of the stricter cash/
    threshold rules compute_pct_bump_for_deal applies, so a deal can
    have a determinable first/final price here even when it's excluded
    from the % bump stat itself (e.g. the final proposal isn't cash)."""
    dated = _dated_proposals(d["proposals"])
    if not dated:
        return None, None
    first_price = _price(dated[0])
    final = _final_entry(dated)
    final_price = _price(final) if final else None
    return first_price, final_price


def compute_final_price_range_for_deal(d: dict) -> tuple[Optional[float], Optional[float]]:
    """The final entry's raw (price_low, price_high) -- distinct from
    compute_first_final_price_for_deal's single combined final_price,
    needed to tell a genuine single price (price_low == price_high)
    apart from a quoted range (price_low != price_high)."""
    dated = _dated_proposals(d["proposals"])
    final = _final_entry(dated)
    if final is None:
        return None, None
    return final["price_low"], final["price_high"]


def compute_pct_bump_for_deal(d: dict) -> tuple[Optional[float], Optional[str]]:
    """Returns (pct, exclusion_reason). reason is None exactly when pct
    is a valid, includable value. For abs_change_over_300pct, pct still
    carries the (excluded) computed value -- useful for a diagnostic
    listing of what got excluded and why; every other exclusion reason
    means pct couldn't be computed at all, so it's None."""
    dated = _dated_proposals(d["proposals"])
    if len(dated) < 2:
        return None, "fewer_than_2_dated_proposals"
    final = _final_entry(dated)
    if final is None or final["consideration_type"] != "cash":
        return None, "not_cash_or_no_final"
    first_price = _price(dated[0])
    final_price = _price(final)
    if first_price is None:
        return None, "missing_first_price"
    if final_price is None:
        return None, "missing_final_price"
    if final_price <= 0:
        return None, "final_price_non_positive"
    if first_price == 0 or first_price < MIN_FIRST_PRICE_USD:
        return None, "first_price_below_10_cents"
    if first_price < MIN_FIRST_PRICE_PCT_OF_FINAL * abs(final_price):
        return None, "first_price_below_5pct_of_final"
    pct = (final_price - first_price) / first_price * 100
    if abs(pct) > MAX_ABS_PCT_CHANGE:
        return pct, "abs_change_over_300pct"
    return pct, None


def pct_bump_bucket(pct: Optional[float]) -> Optional[str]:
    """Histogram bucket label for a % bump value, width 10 (e.g. "0% to
    10%", "-10% to 0%"), with an overflow bucket above 100%. None input
    (not computed, or excluded) yields None, not a bucket -- a consumer
    must check pct_bump_exclusion_reason to tell "excluded" apart from
    "genuinely in a bucket"."""
    if pct is None:
        return None
    if pct > 100:
        return ">100%"
    lower = int(pct // 10) * 10
    return f"{lower}% to {lower + 10}%"


def compute_first_bidder_won_for_deal(d: dict) -> tuple[Optional[bool], Optional[str]]:
    dated = _dated_proposals(d["proposals"])
    bidder_dated = [p for p in dated if p["proposer"] and p["proposer"] != d["target"]]
    if not bidder_dated:
        return None, "no_non_target_proposal"
    final = _final_entry(dated)
    if final is None or not final["proposer"]:
        return None, "no_final_entry"
    first_bidder = bidder_dated[0]["proposer"]
    eventual_acquirer = final["proposer"]
    return (first_bidder.strip().lower() == eventual_acquirer.strip().lower()), None


def _process_start_date(d: dict):
    first_contact = sorted(
        (e for e in d["events"] if e["event_type"] == "first_contact" and e["date_start"]),
        key=lambda e: e["date_start"],
    )
    if first_contact:
        return first_contact[0]["date_start"]
    all_dates = sorted(
        [e["date_start"] for e in d["events"] if e["date_start"]]
        + [p["date_resolved"] for p in d["proposals"] if p["date_resolved"]]
    )
    return all_dates[0] if all_dates else None


def _latest_signing_date(d: dict):
    signings = sorted(
        (e for e in d["events"] if e["event_type"] == "signing" and e["date_start"]),
        key=lambda e: e["date_start"],
    )
    return signings[-1]["date_start"] if signings else None


def _days_between(start, end) -> int:
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)
    return (end - start).days


def compute_days_first_contact_to_signing_for_deal(d: dict) -> tuple[Optional[int], Optional[str]]:
    process_start = _process_start_date(d)
    if process_start is None:
        return None, "no_process_start_date"
    signing_date = _latest_signing_date(d)
    if signing_date is None:
        return None, "no_signing_event"
    days = _days_between(process_start, signing_date)
    if days < 0:
        return days, "negative_duration"
    return days, None


def compute_days_first_proposal_to_signing_for_deal(d: dict) -> tuple[Optional[int], Optional[str]]:
    dated = _dated_proposals(d["proposals"])
    if not dated:
        return None, "no_dated_proposal"
    first_proposal_date = dated[0]["date_resolved"]
    signing_date = _latest_signing_date(d)
    if signing_date is None:
        return None, "no_signing_event"
    days = _days_between(first_proposal_date, signing_date)
    if days < 0:
        return days, "negative_duration"
    return days, None


# --- aggregate stats -----------------------------------------------------


def stat_parties_contacted(deals: list[dict]) -> dict:
    values = [compute_n_parties_contacted_for_deal(d) for d in deals]
    return {
        "definition": "Number of distinct non-target parties named in any first_contact, nda, or discussion event for the deal.",
        "n": len(values),
        **_distribution(values),
        "exclusions": "none -- 0 counted for deals with no such event",
    }


def stat_n_bidders(deals: list[dict]) -> dict:
    values = [compute_n_bidders_for_deal(d) for d in deals]
    return {
        "definition": "Number of distinct non-target proposers across the deal's proposals (parties that actually submitted a priced bid, not just made contact).",
        "n": len(values),
        **_distribution(values),
        "exclusions": "none -- 0 counted for deals with no non-target proposer",
    }


def stat_n_proposals(deals: list[dict]) -> dict:
    values = [compute_n_proposals_for_deal(d) for d in deals]
    return {
        "definition": "Total count of Proposal records (from any proposer, including the target's own counteroffers) extracted for the deal.",
        "n": len(values),
        **_distribution(values),
        "exclusions": "none -- 0 counted for deals with no proposals",
    }


_PCT_BUMP_EXCLUDED_DEAL_REASONS = {
    "final_price_non_positive", "first_price_below_10_cents",
    "first_price_below_5pct_of_final", "abs_change_over_300pct",
}


def stat_pct_increase_cash(deals: list[dict]) -> dict:
    values = []
    excluded_counts = {
        "not_cash_or_no_final": 0, "missing_first_price": 0, "missing_final_price": 0,
        "fewer_than_2_dated_proposals": 0, "first_price_below_10_cents": 0,
        "first_price_below_5pct_of_final": 0, "final_price_non_positive": 0,
        "abs_change_over_300pct": 0,
    }
    excluded_deals = []
    flagged_for_review = []
    for d in deals:
        pct, reason = compute_pct_bump_for_deal(d)
        if reason is not None:
            excluded_counts[reason] += 1
            if reason in _PCT_BUMP_EXCLUDED_DEAL_REASONS:
                first_price, final_price = compute_first_final_price_for_deal(d)
                entry = {"deal_name": d["deal_name"], "first_price": first_price, "final_price": final_price, "reason": reason}
                if reason == "abs_change_over_300pct":
                    entry["pct_increase"] = pct
                excluded_deals.append(entry)
            continue
        if pct <= REVIEW_PCT_DROP_THRESHOLD:
            first_price, final_price = compute_first_final_price_for_deal(d)
            flagged_for_review.append({"deal_name": d["deal_name"], "first_price": first_price, "final_price": final_price, "pct_increase": pct})
        values.append((d["deal_name"], pct))

    pct_values = [v for _, v in values]
    top = sorted(values, key=lambda t: t[1], reverse=True)[:N_OUTLIERS]
    return {
        "definition": "Percent change from the earliest dated proposal's price (price_high if present else price_low) to the final (accepted, else latest-dated) proposal's price, restricted to deals whose final proposal is cash and where both prices are known.",
        "n": len(pct_values),
        **_distribution(pct_values),
        "top_outliers": [{"deal_name": name, "pct_increase": v} for name, v in top],
        "flagged_for_review_drop_90pct_or_more": flagged_for_review,
        "exclusions": excluded_counts,
        "excluded_deals": excluded_deals,
    }


def stat_first_bidder_is_acquirer(deals: list[dict]) -> dict:
    matches = 0
    n = 0
    excluded = {"no_non_target_proposal": 0, "no_final_entry": 0}
    for d in deals:
        won, reason = compute_first_bidder_won_for_deal(d)
        if reason is not None:
            excluded[reason] += 1
            continue
        n += 1
        if won:
            matches += 1
    return {
        "definition": "Share of deals where the proposer of the earliest dated non-target proposal is the same (case-insensitive) as the proposer of the final (accepted, else latest-dated) proposal.",
        "n": n,
        "pct_first_bidder_is_eventual_acquirer": (matches / n * 100) if n else None,
        "exclusions": excluded,
    }


def stat_days_first_contact_to_signing(deals: list[dict]) -> dict:
    values = []
    excluded_counts = {"no_process_start_date": 0, "no_signing_event": 0, "negative_duration": 0}
    flagged_for_review = []
    for d in deals:
        days, reason = compute_days_first_contact_to_signing_for_deal(d)
        if reason is not None:
            excluded_counts[reason] += 1
            continue
        if days > MAX_DAYS_FOR_REVIEW:
            flagged_for_review.append({"deal_name": d["deal_name"], "days": days})
        values.append((d["deal_name"], days))

    day_values = [v for _, v in values]
    top = sorted(values, key=lambda t: t[1], reverse=True)[:N_OUTLIERS]
    return {
        "definition": "Days from the deal's process-start date (earliest first_contact event, else the earliest dated event/proposal of any kind) to its latest signing event.",
        "n": len(day_values),
        **_distribution(day_values),
        "top_outliers": [{"deal_name": name, "days": v} for name, v in top],
        "flagged_for_review_over_2000_days": flagged_for_review,
        "exclusions": excluded_counts,
    }


def stat_days_first_proposal_to_signing(deals: list[dict]) -> dict:
    values = []
    excluded_counts = {"no_dated_proposal": 0, "no_signing_event": 0, "negative_duration": 0}
    flagged_for_review = []
    for d in deals:
        days, reason = compute_days_first_proposal_to_signing_for_deal(d)
        if reason is not None:
            excluded_counts[reason] += 1
            continue
        if days > MAX_DAYS_FOR_REVIEW:
            flagged_for_review.append({"deal_name": d["deal_name"], "days": days})
        values.append((d["deal_name"], days))

    day_values = [v for _, v in values]
    top = sorted(values, key=lambda t: t[1], reverse=True)[:N_OUTLIERS]
    return {
        "definition": "Days from the deal's earliest dated proposal to its latest signing event -- a cleaner anchor than first_contact, which many deals never extract.",
        "n": len(day_values),
        **_distribution(day_values),
        "top_outliers": [{"deal_name": name, "days": v} for name, v in top],
        "flagged_for_review_over_2000_days": flagged_for_review,
        "exclusions": excluded_counts,
    }


def compute_all() -> dict:
    with connect() as conn:
        deals = _fetch_canonical_deals(conn)
    return {
        "n_canonical_deals": len(deals),
        "parties_contacted": stat_parties_contacted(deals),
        "bidders_who_submitted_a_proposal": stat_n_bidders(deals),
        "proposals_per_deal": stat_n_proposals(deals),
        "pct_increase_cash_deals": stat_pct_increase_cash(deals),
        "pct_first_bidder_is_eventual_acquirer": stat_first_bidder_is_acquirer(deals),
        "days_first_contact_to_signing": stat_days_first_contact_to_signing(deals),
        "days_first_proposal_to_signing": stat_days_first_proposal_to_signing(deals),
    }


def main() -> None:
    from src.deal_metrics import refresh_all

    result = compute_all()
    print(json.dumps(result, indent=2, default=str))
    summary = refresh_all()
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
