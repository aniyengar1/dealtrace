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
can produce a nonsense outlier -- see QUALITY_FLAGS below).

Target-side placeholder terms ("the Company", "Target", "Board", etc.)
are resolved to each deal's own target name before any proposer/
recipient comparison via src.entity_match.is_same_entity, not exact
string equality -- extracted text uses informal short names ("Knoll")
that never exactly match EDGAR's raw legal name ("KNOLL INC").
"""

import json
import statistics
from datetime import date
from typing import Optional

import psycopg

from src import validate
from src.entity_match import is_acronym_of, is_same_entity
from src.env import load_env
from src.load_db import connect

load_env()

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


def _fetch_canonical_deals(conn: psycopg.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT d.id, d.slug, d.deal_name, d.target, d.acquirer FROM deals d WHERE d.is_canonical"
    ).fetchall()
    deals = []
    for deal_id, slug, deal_name, target, acquirer in rows:
        events = conn.execute(
            """
            SELECT e.date_start, e.event_type, e.parties
            FROM events e
            JOIN extraction_runs r ON r.id = e.run_id
            WHERE r.deal_id = %s AND e.passed
            """,
            (deal_id,),
        ).fetchall()
        proposals = conn.execute(
            """
            SELECT p.date_resolved, p.proposer, p.recipient, p.price_low, p.price_high,
                   p.consideration_type, p.status
            FROM proposals p
            JOIN extraction_runs r ON r.id = p.run_id
            WHERE r.deal_id = %s AND p.passed
            """,
            (deal_id,),
        ).fetchall()
        deals.append(
            {
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


def stat_parties_contacted(deals: list[dict]) -> dict:
    values = []
    for d in deals:
        contacted = {
            name
            for e in d["events"]
            if e["event_type"] in CONTACT_EVENT_TYPES
            for name in e["parties"]
            if name and name != d["target"]
        }
        values.append(len(contacted))
    return {
        "definition": "Number of distinct non-target parties named in any first_contact, nda, or discussion event for the deal.",
        "n": len(values),
        **_distribution(values),
        "exclusions": "none -- 0 counted for deals with no such event",
    }


def stat_n_bidders(deals: list[dict]) -> dict:
    values = []
    for d in deals:
        bidders = {p["proposer"] for p in d["proposals"] if p["proposer"] and p["proposer"] != d["target"]}
        values.append(len(bidders))
    return {
        "definition": "Number of distinct non-target proposers across the deal's proposals (parties that actually submitted a priced bid, not just made contact).",
        "n": len(values),
        **_distribution(values),
        "exclusions": "none -- 0 counted for deals with no non-target proposer",
    }


def stat_n_proposals(deals: list[dict]) -> dict:
    values = [len(d["proposals"]) for d in deals]
    return {
        "definition": "Total count of Proposal records (from any proposer, including the target's own counteroffers) extracted for the deal.",
        "n": len(values),
        **_distribution(values),
        "exclusions": "none -- 0 counted for deals with no proposals",
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
        dated = _dated_proposals(d["proposals"])
        if len(dated) < 2:
            excluded_counts["fewer_than_2_dated_proposals"] += 1
            continue
        final = _final_entry(dated)
        if final is None or final["consideration_type"] != "cash":
            excluded_counts["not_cash_or_no_final"] += 1
            continue
        first = dated[0]
        first_price = _price(first)
        final_price = _price(final)
        if first_price is None:
            excluded_counts["missing_first_price"] += 1
            continue
        if final_price is None:
            excluded_counts["missing_final_price"] += 1
            continue
        if final_price <= 0:
            excluded_counts["final_price_non_positive"] += 1
            excluded_deals.append({"deal_name": d["deal_name"], "first_price": first_price, "final_price": final_price, "reason": "final_price_non_positive"})
            continue
        if first_price == 0 or first_price < MIN_FIRST_PRICE_USD:
            excluded_counts["first_price_below_10_cents"] += 1
            excluded_deals.append({"deal_name": d["deal_name"], "first_price": first_price, "final_price": final_price, "reason": "first_price_below_10_cents"})
            continue
        if first_price < MIN_FIRST_PRICE_PCT_OF_FINAL * abs(final_price):
            excluded_counts["first_price_below_5pct_of_final"] += 1
            excluded_deals.append({"deal_name": d["deal_name"], "first_price": first_price, "final_price": final_price, "reason": "first_price_below_5pct_of_final"})
            continue
        pct = (final_price - first_price) / first_price * 100
        if abs(pct) > MAX_ABS_PCT_CHANGE:
            excluded_counts["abs_change_over_300pct"] += 1
            excluded_deals.append({"deal_name": d["deal_name"], "first_price": first_price, "final_price": final_price, "pct_increase": pct, "reason": "abs_change_over_300pct"})
            continue
        if pct <= REVIEW_PCT_DROP_THRESHOLD:
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
        dated = _dated_proposals(d["proposals"])
        bidder_dated = [p for p in dated if p["proposer"] and p["proposer"] != d["target"]]
        if not bidder_dated:
            excluded["no_non_target_proposal"] += 1
            continue
        final = _final_entry(dated)
        if final is None or not final["proposer"]:
            excluded["no_final_entry"] += 1
            continue
        first_bidder = bidder_dated[0]["proposer"]
        eventual_acquirer = final["proposer"]
        n += 1
        if first_bidder.strip().lower() == eventual_acquirer.strip().lower():
            matches += 1
    return {
        "definition": "Share of deals where the proposer of the earliest dated non-target proposal is the same (case-insensitive) as the proposer of the final (accepted, else latest-dated) proposal.",
        "n": n,
        "pct_first_bidder_is_eventual_acquirer": (matches / n * 100) if n else None,
        "exclusions": excluded,
    }


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


def stat_days_first_contact_to_signing(deals: list[dict]) -> dict:
    values = []
    excluded_counts = {"no_process_start_date": 0, "no_signing_event": 0, "negative_duration": 0}
    flagged_for_review = []
    for d in deals:
        process_start = _process_start_date(d)
        if process_start is None:
            excluded_counts["no_process_start_date"] += 1
            continue
        signing_date = _latest_signing_date(d)
        if signing_date is None:
            excluded_counts["no_signing_event"] += 1
            continue
        days = _days_between(process_start, signing_date)
        if days < 0:
            excluded_counts["negative_duration"] += 1
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
        dated = _dated_proposals(d["proposals"])
        if not dated:
            excluded_counts["no_dated_proposal"] += 1
            continue
        first_proposal_date = dated[0]["date_resolved"]
        signing_date = _latest_signing_date(d)
        if signing_date is None:
            excluded_counts["no_signing_event"] += 1
            continue
        days = _days_between(first_proposal_date, signing_date)
        if days < 0:
            excluded_counts["negative_duration"] += 1
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
    print(json.dumps(compute_all(), indent=2, default=str))


if __name__ == "__main__":
    main()
