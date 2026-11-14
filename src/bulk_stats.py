"""Five headline stats across the loaded bulk deals (deals.slug LIKE
'bulk_%'), computed directly from Postgres after src.load_bulk has run.

    python -m src.bulk_stats

Mirrors the established conventions in apps/web/src/lib/dealSummary.ts
(nBidders, firstBidProposal/finalBidProposal via price_high ?? price_low
and accepted-else-last-dated, daysFirstContactToSigning via
first_contact-else-earliest-date to latest signing) rather than
inventing new definitions, except where this task's own spec is
explicitly narrower (percent-increase is restricted to cash deals with
both prices, which dealSummary.ts's pctChange does not do).

Target-side placeholder terms ("the Company", "Target", "Board", etc.)
are resolved to each deal's own target name before any proposer/
recipient comparison -- bulk extraction skips the normalization pass
that the curated-deal pipeline runs, so literal placeholders would
otherwise make every deal's "first bidder" or "eventual acquirer"
compare equal to each other instead of to the target.
"""

import json
import statistics
from datetime import date
from typing import Optional

import psycopg

from src import validate
from src.env import load_env
from src.load_db import connect

load_env()


def _resolve_target(name: Optional[str], target: str) -> Optional[str]:
    if name and name.strip().lower() in validate._TARGET_DEFINED_TERMS:
        return target
    return name


def _fetch_bulk_deals(conn: psycopg.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT d.id, d.slug, d.target, d.acquirer
        FROM deals d
        WHERE d.slug LIKE 'bulk_%'
        """
    ).fetchall()
    deals = []
    for deal_id, slug, target, acquirer in rows:
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
                "target": target,
                "acquirer": acquirer,
                "events": [{"date_start": e[0], "event_type": e[1], "parties": e[2]} for e in events],
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


def stat_n_bidders(deals: list[dict]) -> dict:
    values = []
    for d in deals:
        bidders = {p["proposer"] for p in d["proposals"] if p["proposer"] and p["proposer"] != d["target"]}
        values.append(len(bidders))
    return {"n": len(values), "median": statistics.median(values) if values else None, "exclusions": "none -- 0 counted for deals with no non-target proposer"}


def stat_n_proposals(deals: list[dict]) -> dict:
    values = [len(d["proposals"]) for d in deals]
    return {"n": len(values), "median": statistics.median(values) if values else None, "exclusions": "none -- 0 counted for deals with no proposals"}


def stat_pct_increase_cash(deals: list[dict]) -> dict:
    values = []
    excluded = {"not_cash_or_no_final": 0, "missing_first_price": 0, "missing_final_price": 0, "fewer_than_2_dated_proposals": 0}
    for d in deals:
        dated = _dated_proposals(d["proposals"])
        if len(dated) < 2:
            excluded["fewer_than_2_dated_proposals"] += 1
            continue
        final = _final_entry(dated)
        if final is None or final["consideration_type"] != "cash":
            excluded["not_cash_or_no_final"] += 1
            continue
        first = dated[0]
        first_price = _price(first)
        final_price = _price(final)
        if first_price is None:
            excluded["missing_first_price"] += 1
            continue
        if final_price is None:
            excluded["missing_final_price"] += 1
            continue
        if first_price == 0:
            excluded["missing_first_price"] += 1
            continue
        values.append((final_price - first_price) / first_price * 100)
    return {
        "n": len(values),
        "median_pct_increase": statistics.median(values) if values else None,
        "exclusions": excluded,
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
        "n": n,
        "pct_first_bidder_is_eventual_acquirer": (matches / n * 100) if n else None,
        "exclusions": excluded,
    }


def stat_days_first_contact_to_signing(deals: list[dict]) -> dict:
    values = []
    excluded = {"no_process_start_date": 0, "no_signing_event": 0}
    for d in deals:
        events = d["events"]
        first_contact = sorted(
            (e for e in events if e["event_type"] == "first_contact" and e["date_start"]),
            key=lambda e: e["date_start"],
        )
        process_start = first_contact[0]["date_start"] if first_contact else None
        if process_start is None:
            all_dates = sorted(
                [e["date_start"] for e in events if e["date_start"]]
                + [p["date_resolved"] for p in d["proposals"] if p["date_resolved"]]
            )
            process_start = all_dates[0] if all_dates else None
        if process_start is None:
            excluded["no_process_start_date"] += 1
            continue

        signings = sorted(
            (e for e in events if e["event_type"] == "signing" and e["date_start"]),
            key=lambda e: e["date_start"],
        )
        if not signings:
            excluded["no_signing_event"] += 1
            continue
        signing_date = signings[-1]["date_start"]

        if isinstance(process_start, date):
            days = (signing_date - process_start).days
        else:
            days = (date.fromisoformat(signing_date) - date.fromisoformat(process_start)).days
        values.append(days)
    return {"n": len(values), "median_days": statistics.median(values) if values else None, "exclusions": excluded}


def compute_all() -> dict:
    with connect() as conn:
        deals = _fetch_bulk_deals(conn)
    return {
        "n_loaded_deals": len(deals),
        "median_bidders_contacted": stat_n_bidders(deals),
        "median_proposals_per_deal": stat_n_proposals(deals),
        "median_pct_increase_cash_deals": stat_pct_increase_cash(deals),
        "pct_first_bidder_is_eventual_acquirer": stat_first_bidder_is_acquirer(deals),
        "median_days_first_contact_to_signing": stat_days_first_contact_to_signing(deals),
    }


def main() -> None:
    print(json.dumps(compute_all(), indent=2, default=str))


if __name__ == "__main__":
    main()
