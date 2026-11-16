"""Populates deal_metrics (one row per deal) and headline_stats (one
row per aggregate stat) -- the Postgres-side single source of truth
for site stats, so the website never needs to recompute this logic
itself.

    python -m src.deal_metrics

Every per-deal value here is computed by the same compute_*_for_deal
functions src.bulk_stats's aggregates use, so a deal_metrics row and
the headline_stats aggregates it feeds into can never silently drift
apart from each other.
"""

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg

from src import bulk_stats
from src.dedup_deals import _is_generic
from src.display_name import clean_display_name
from src.entity_match import is_acronym_of, is_anonymized_placeholder, is_same_entity
from src.env import load_env
from src.load_db import connect
from src.run import DEALS

UNDISCLOSED = "Undisclosed"

# Curated deals (src.run.DEALS) carry a hand-verified target/acquirer
# pair -- always use those over the heuristic resolver below, which was
# built for ~1000 unreviewed bulk extractions and has no business
# overriding a gold deal. DEALS[slug]["acquirer"] is sometimes a
# shorthand ("Consortium" for Zendesk, "Vista" for Citrix) that the
# richer deal_name spells out in full ("Hellman & Friedman and
# Permira's Acquisition of Zendesk") -- parsed out here rather than
# hardcoded a second time, so the two can't drift apart. Falls back to
# the raw acquirer field if deal_name doesn't parse as expected.
_ACQUISITION_OF_RE = re.compile(r"^(.*)'s Acquisition of (.+)$")


def _curated_display_names(slug: str) -> tuple[str, str]:
    deal = DEALS[slug]
    target_display = deal["target"]
    match = _ACQUISITION_OF_RE.match(deal["deal_name"])
    if match and match.group(2).strip() == target_display.strip():
        acquirer_display = match.group(1).strip()
    else:
        acquirer_display = deal["acquirer"]
    return target_display, acquirer_display

# Minimum plausible per-share final price for price_plausible -- a
# final_price at or below this is almost certainly a stray cents-level
# or unit-mismatched extraction, not a real deal price.
MIN_PLAUSIBLE_FINAL_PRICE_USD = 0.10

load_env()

OUTPUT_PATH = Path("data/output/stats/headline_stats.json")

# Small, deliberately conservative set of short-form/ticker acquirer
# names this pipeline has produced where the full legal name is well
# known but never appears anywhere in the deal's own extracted text
# (so the local-evidence fallback below has nothing to resolve against)
# -- e.g. "NSC" for Nippon Steel never gets spelled out in the US
# Steel background section at all. Deliberately small: a wrong entry
# here would be worse than falling back to the short form, so this only
# includes names verified with high confidence, not a guess.
KNOWN_SHORT_NAME_EXPANSIONS = {
    "NSC": "Nippon Steel Corporation",
    "PSKY": "Paramount Skydance Corporation",
}

# Trailing words that mean the "longer" mention is a REFERENCE to the
# acquirer (its board, a committee, its shareholders, its manager...),
# not a fuller version of its own legal name -- "SeaSpine Board" must
# never win over "SeaSpine" just for being longer. Checked against the
# last significant word only, so a real name that merely CONTAINS one
# of these mid-string ("Brookfield Asset Management Inc.") is untouched.
_ORG_REFERENCE_WORDS = {
    "board", "boards", "directors", "committee", "committees", "special", "transactions",
    "transaction", "stockholders", "stockholder", "shareholders", "shareholder",
    "management", "manager", "managers", "advisor", "advisors", "adviser", "advisers",
    "trustee", "trustees", "ultimate", "parent", "strategic", "review", "compensation",
    "significant", "family", "independent", "conflicts", "affiliate", "affiliates",
    "fund", "consortium", "sub", "subs", "member", "members", "holder", "holders",
    "seller", "sellers",
}
_TRAILING_ALPHA_WORD_RE = re.compile(r"[A-Za-z']+(?!.*[A-Za-z])")


def _is_safe_fuller_name(candidate: str, base: str) -> bool:
    """True if `candidate` looks like a more complete form of the exact
    same legal name as `base`: a literal prefix (not a fuzzy/stripped
    one; that was tried and over-matched, e.g. "Enghouse Systems
    Limited" -> "Enghouse Interactive, Inc." once "Systems" got treated
    as a strippable legal suffix), separated from the extra part by
    punctuation/whitespace rather than running directly into another
    letter (rejects "FSK" -> "FSKR", a DIFFERENT fund's ticker that
    happens to start with this one's, not a fuller form of it), with
    the extra part containing at least one letter (rejects "GBDC" ->
    "GBDC 3", a different numbered sibling fund, not this one with
    more words), no " and " anywhere in it (would mean combining two
    different sponsors' names into one), not itself an anonymized
    placeholder ("Transocean" -> "Transocean Party A"), and ending in a
    non-organizational-reference word ("SeaSpine" -> "SeaSpine Board",
    its board of directors, not a fuller version of its own name)."""
    base_norm = base.strip().lower()
    candidate_norm = candidate.strip().lower()
    if candidate_norm == base_norm or not candidate_norm.startswith(base_norm):
        return False
    separator = candidate[len(base)] if len(candidate) > len(base) else ""
    if separator.isalnum():
        return False
    extra = candidate[len(base):].strip()
    if not extra or not any(c.isalpha() for c in extra):
        return False
    if " and " in f" {extra.lower()} " or is_anonymized_placeholder(extra):
        return False
    match = _TRAILING_ALPHA_WORD_RE.search(extra)
    trailing_word = match.group(0).lower() if match else ""
    return trailing_word not in _ORG_REFERENCE_WORDS


_COMMITTEE_RE = re.compile(r"\bcommittee\b", re.IGNORECASE)


def _is_invalid_acquirer_display(name: str, target: str) -> bool:
    """True when `name` is unusable as a public-facing acquirer name:
    a generic role placeholder ("Parent", "Buyer", "Purchaser", ...),
    an anonymized placeholder ("Company A"), a board/special/conflicts
    committee reference, a ticker/acronym/short-name that's actually
    the target itself, or the target's own (cleaned) name verbatim."""
    if not name:
        return True
    if _is_generic(name) or is_anonymized_placeholder(name):
        return True
    if _COMMITTEE_RE.search(name):
        return True
    if is_same_entity(name, target) or is_acronym_of(name, target):
        return True
    if clean_display_name(name).strip().lower() == clean_display_name(target).strip().lower():
        return True
    return False


def resolve_acquirer_display(acquirer: str, target: str, proposals: list[dict], events: list[dict]) -> str:
    """"Best available" full name for the stored (possibly short-form)
    acquirer: a curated expansion if we have high-confidence outside
    knowledge of one, else the longest locally-mentioned name that is a
    literal, safe completion of it (a deal's own text sometimes uses
    both "Cisco" and "Cisco Systems, Inc." -- prefer the fuller one),
    else the stored value unchanged -- cleaned (suffix-stripped,
    title-cased) the same way target_display is, and replaced with
    "Undisclosed" if what's left is a placeholder, a committee, or the
    target itself under another name, rather than ever showing one of
    those to a site visitor as if it were a real acquirer."""
    if acquirer in KNOWN_SHORT_NAME_EXPANSIONS:
        resolved = KNOWN_SHORT_NAME_EXPANSIONS[acquirer]
    else:
        mentioned = set()
        for p in proposals:
            mentioned.add(p.get("proposer"))
            mentioned.add(p.get("recipient"))
        for e in events:
            mentioned.update(e.get("parties") or [])
        mentioned.discard(None)

        candidates = [acquirer] + [m for m in mentioned if m != target and _is_safe_fuller_name(m, acquirer)]
        resolved = max(candidates, key=len)

    if _is_invalid_acquirer_display(resolved, target):
        return UNDISCLOSED
    return clean_display_name(resolved)


def compute_price_plausible(final_price: Optional[float], final_price_low: Optional[float], final_price_high: Optional[float]) -> Optional[bool]:
    """False when the final price is at or below the implausibly-low
    threshold, or when the final proposal is a quoted range
    (price_low != price_high) rather than a single settled price.
    None (not applicable) when there's no final price at all."""
    if final_price is None:
        return None
    if final_price <= MIN_PLAUSIBLE_FINAL_PRICE_USD:
        return False
    if final_price_low is not None and final_price_high is not None and final_price_low != final_price_high:
        return False
    return True


def compute_metrics_for_deal(d: dict) -> dict:
    first_price, final_price = bulk_stats.compute_first_final_price_for_deal(d)
    final_price_low, final_price_high = bulk_stats.compute_final_price_range_for_deal(d)
    pct_bump, pct_bump_reason = bulk_stats.compute_pct_bump_for_deal(d)
    days_contact, _ = bulk_stats.compute_days_first_contact_to_signing_for_deal(d)
    days_proposal, _ = bulk_stats.compute_days_first_proposal_to_signing_for_deal(d)
    first_bidder_won, _ = bulk_stats.compute_first_bidder_won_for_deal(d)

    if d["slug"] in DEALS:
        target_display, acquirer_display = _curated_display_names(d["slug"])
    else:
        target_display = clean_display_name(d["target"])
        acquirer_display = resolve_acquirer_display(d["acquirer"], d["target"], d["proposals"], d["events"])

    return {
        "target_display": target_display,
        "acquirer_display": acquirer_display,
        "n_parties_contacted": bulk_stats.compute_n_parties_contacted_for_deal(d),
        "n_bidders": bulk_stats.compute_n_bidders_for_deal(d),
        "n_proposals": bulk_stats.compute_n_proposals_for_deal(d),
        "first_price": first_price,
        "final_price": final_price,
        "price_plausible": compute_price_plausible(final_price, final_price_low, final_price_high),
        "pct_bump": pct_bump if pct_bump_reason is None else None,
        "pct_bump_exclusion_reason": pct_bump_reason,
        "pct_bump_bucket": bulk_stats.pct_bump_bucket(pct_bump if pct_bump_reason is None else None),
        "days_first_contact_to_signing": days_contact,
        "days_first_proposal_to_signing": days_proposal,
        "first_bidder_won": first_bidder_won,
    }


def refresh_deal_metrics(conn: psycopg.Connection) -> int:
    deals = bulk_stats.fetch_deals(conn, canonical_only=False)
    is_canonical_by_id = {
        row[0]: row[1] for row in conn.execute("SELECT id, is_canonical FROM deals").fetchall()
    }
    n = 0
    for d in deals:
        m = compute_metrics_for_deal(d)
        conn.execute(
            """
            INSERT INTO deal_metrics (
                deal_id, is_canonical, target_display, acquirer_display, n_parties_contacted, n_bidders,
                n_proposals, first_price, final_price, price_plausible, pct_bump, pct_bump_exclusion_reason,
                pct_bump_bucket, days_first_contact_to_signing, days_first_proposal_to_signing,
                first_bidder_won, computed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (deal_id) DO UPDATE SET
                is_canonical = EXCLUDED.is_canonical,
                target_display = EXCLUDED.target_display,
                acquirer_display = EXCLUDED.acquirer_display,
                n_parties_contacted = EXCLUDED.n_parties_contacted,
                n_bidders = EXCLUDED.n_bidders,
                n_proposals = EXCLUDED.n_proposals,
                first_price = EXCLUDED.first_price,
                final_price = EXCLUDED.final_price,
                price_plausible = EXCLUDED.price_plausible,
                pct_bump = EXCLUDED.pct_bump,
                pct_bump_exclusion_reason = EXCLUDED.pct_bump_exclusion_reason,
                pct_bump_bucket = EXCLUDED.pct_bump_bucket,
                days_first_contact_to_signing = EXCLUDED.days_first_contact_to_signing,
                days_first_proposal_to_signing = EXCLUDED.days_first_proposal_to_signing,
                first_bidder_won = EXCLUDED.first_bidder_won,
                computed_at = now()
            """,
            (
                d["deal_id"], is_canonical_by_id[d["deal_id"]], m["target_display"], m["acquirer_display"],
                m["n_parties_contacted"], m["n_bidders"], m["n_proposals"],
                m["first_price"], m["final_price"], m["price_plausible"], m["pct_bump"], m["pct_bump_exclusion_reason"],
                m["pct_bump_bucket"], m["days_first_contact_to_signing"],
                m["days_first_proposal_to_signing"], m["first_bidder_won"],
            ),
        )
        n += 1
    return n


# Maps compute_all()'s top-level keys to the scalar field each stat's
# "headline value" lives in when it isn't a min/p25/median/p75/max
# distribution -- pct_first_bidder_is_eventual_acquirer is a single
# percentage, not a distribution, so it's stored in `median` with the
# other four left NULL (see db/migrations/0015_deal_metrics.sql).
_SCALAR_STAT_VALUE_KEYS = {
    "pct_first_bidder_is_eventual_acquirer": "pct_first_bidder_is_eventual_acquirer",
}


def _code_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def refresh_headline_stats(conn: psycopg.Connection, stats: dict, generated_at: str, code_commit: str) -> int:
    n = 0
    for name, stat in stats.items():
        if name == "n_canonical_deals":
            continue
        if name in _SCALAR_STAT_VALUE_KEYS:
            value = stat[_SCALAR_STAT_VALUE_KEYS[name]]
            p25 = p75 = min_ = max_ = None
            median = value
        else:
            p25, median, p75 = stat.get("p25"), stat.get("median"), stat.get("p75")
            min_, max_ = stat.get("min"), stat.get("max")
        exclusions = stat.get("exclusions", {})
        conn.execute(
            """
            INSERT INTO headline_stats (name, n, p25, median, p75, min, max, exclusions, generated_at, code_commit)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET
                n = EXCLUDED.n, p25 = EXCLUDED.p25, median = EXCLUDED.median, p75 = EXCLUDED.p75,
                min = EXCLUDED.min, max = EXCLUDED.max, exclusions = EXCLUDED.exclusions,
                generated_at = EXCLUDED.generated_at, code_commit = EXCLUDED.code_commit
            """,
            (name, stat["n"], p25, median, p75, min_, max_, json.dumps(exclusions, default=str), generated_at, code_commit),
        )
        n += 1
    return n


def refresh_all() -> dict:
    stats = bulk_stats.compute_all()
    generated_at = datetime.now(timezone.utc).isoformat()
    code_commit = _code_commit()

    with connect() as conn:
        n_metrics = refresh_deal_metrics(conn)
        n_stats = refresh_headline_stats(conn, stats, generated_at, code_commit)
        conn.commit()

    payload = {
        "generated_at": generated_at,
        "code_commit": code_commit,
        "methodology_doc": "docs/bulk_stats_methodology.md",
        "stats": stats,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, default=str))

    return {"n_deal_metrics_rows": n_metrics, "n_headline_stats_rows": n_stats, "json_path": str(OUTPUT_PATH)}


def main() -> None:
    print(json.dumps(refresh_all(), indent=2, default=str))


if __name__ == "__main__":
    main()
