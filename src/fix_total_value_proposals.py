"""Re-examines every loaded proposal's price_low/price_high and moves a
value into total_value_low/high (instead of leaving it as a per-share
price) when it's implausible as one relative to the deal's own final
price: > 20x the deal's final per-share price, or > $1,000/share
outright. Catches the subtler version of the Diamondback/Endeavor
overflow case -- an enterprise-value figure (e.g. "$115 million")
small enough to fit NUMERIC(14,4) without erroring, so src.load_db's
load-time overflow check (>= 10^10) never saw it, but still nonsensical
as a per-share price next to a real ~$4-55/share final price.

    python -m src.fix_total_value_proposals

Idempotent: a proposal already holding its value in total_value_* (with
price_low/high already NULL there) has nothing left to move on a
second run.
"""

import json

import psycopg

from src.bulk_stats import _dated_proposals, _final_entry, _price
from src.env import load_env
from src.load_db import connect

load_env()

RATIO_THRESHOLD = 20.0
ABSOLUTE_THRESHOLD_USD = 1000.0


def _is_implausible_per_share(value: float, final_price: float | None) -> bool:
    if value > ABSOLUTE_THRESHOLD_USD:
        return True
    if final_price is not None and final_price > 0 and value > RATIO_THRESHOLD * final_price:
        return True
    return False


def _deal_final_price(conn: psycopg.Connection, deal_id: str) -> float | None:
    rows = conn.execute(
        """
        SELECT p.date_resolved, p.price_low, p.price_high, p.status
        FROM proposals p JOIN extraction_runs r ON r.id = p.run_id
        WHERE r.deal_id = %s AND p.passed
        """,
        (deal_id,),
    ).fetchall()
    proposals = [
        {"date_resolved": r[0], "price_low": float(r[1]) if r[1] is not None else None,
         "price_high": float(r[2]) if r[2] is not None else None, "status": r[3]}
        for r in rows
    ]
    dated = _dated_proposals(proposals)
    final = _final_entry(dated)
    return _price(final) if final else None


def main() -> None:
    n_moved_proposals = 0
    n_fields_moved = 0
    moved_details = []

    with connect() as conn:
        deal_ids = [row[0] for row in conn.execute("SELECT id FROM deals").fetchall()]

        for deal_id in deal_ids:
            final_price = _deal_final_price(conn, deal_id)

            proposals = conn.execute(
                """
                SELECT p.id, p.date_text, p.proposer, p.recipient, p.price_low, p.price_high
                FROM proposals p JOIN extraction_runs r ON r.id = p.run_id
                WHERE r.deal_id = %s AND (p.price_low IS NOT NULL OR p.price_high IS NOT NULL)
                """,
                (deal_id,),
            ).fetchall()

            for proposal_id, date_text, proposer, recipient, price_low, price_high in proposals:
                price_low = float(price_low) if price_low is not None else None
                price_high = float(price_high) if price_high is not None else None

                new_price_low, new_total_low = price_low, None
                new_price_high, new_total_high = price_high, None
                moved_this = False

                if price_low is not None and _is_implausible_per_share(price_low, final_price):
                    new_price_low, new_total_low = None, price_low
                    moved_this = True
                if price_high is not None and _is_implausible_per_share(price_high, final_price):
                    new_price_high, new_total_high = None, price_high
                    moved_this = True

                if not moved_this:
                    continue

                conn.execute(
                    """
                    UPDATE proposals SET
                        price_low = %s, price_high = %s,
                        total_value_low = coalesce(total_value_low, %s),
                        total_value_high = coalesce(total_value_high, %s),
                        failure_reasons = failure_reasons ||
                            ARRAY['price reclassified as total/enterprise value, not per-share (see src.fix_total_value_proposals)']
                    WHERE id = %s
                    """,
                    (new_price_low, new_price_high, new_total_low, new_total_high, proposal_id),
                )
                n_moved_proposals += 1
                n_fields_moved += int(new_total_low is not None) + int(new_total_high is not None)
                moved_details.append(
                    {
                        "proposal_id": str(proposal_id), "date": date_text, "proposer": proposer, "recipient": recipient,
                        "old_price_low": price_low, "old_price_high": price_high, "deal_final_price": final_price,
                    }
                )

        conn.commit()

    print(json.dumps({"n_proposals_moved": n_moved_proposals, "n_fields_moved": n_fields_moved, "details": moved_details}, indent=2, default=str))


if __name__ == "__main__":
    main()
