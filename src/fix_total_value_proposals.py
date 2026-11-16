"""Re-examines every loaded proposal's price_low/price_high and moves a
value into total_value_low/high (instead of leaving it as a per-share
price) when it's implausible as one relative to the deal's own final
price: > 20x the deal's final per-share price, > $1,000/share outright,
or its own source_quotes literally say "million"/"billion" (a deal
where EVERY proposal is a consistent "$X million" aggregate valuation,
e.g. Werewolf Therapeutics/Ambros's $5.5M/$47.5M/$50.0M figures, has no
internal outlier to catch via the ratio/absolute checks -- they're all
mutually consistent with each other, just wrong in an absolute sense --
but the quote that produced the number says so directly). Catches the
subtler version of the Diamondback/Endeavor overflow case -- an
enterprise-value figure small enough to fit NUMERIC(14,4) without
erroring, so src.load_db's load-time overflow check (>= 10^10) never
saw it, but still nonsensical as a per-share price.

    python -m src.fix_total_value_proposals

Idempotent: a proposal already holding its value in total_value_* (with
price_low/high already NULL there) has nothing left to move on a
second run.
"""

import json
import re

import psycopg

from src.bulk_stats import _dated_proposals, _final_entry, _price
from src.env import load_env
from src.load_db import connect

load_env()

RATIO_THRESHOLD = 20.0
ABSOLUTE_THRESHOLD_USD = 1000.0
_MILLION_BILLION_RE = re.compile(r"\b(million|billion)\b", re.IGNORECASE)
# Up to 4 words allowed between "per"/"each" and "share(s)" -- real
# filings often say "per issued and outstanding share", not just
# "per share" (Aya/Cross Country: "$18.00 per issued and outstanding
# share" was missed by a stricter version of this regex, nearly
# causing a correct price to be wrongly reclassified). "per-share" is
# also common with a hyphen instead of whitespace (Cumberland/Apotex:
# "implied a per-share value of approximately $6.68" was missed by a
# whitespace-only version, which would have destroyed an already-
# correctly-extracted per-share figure).
_PER_SHARE_RE = re.compile(
    r"per[\s-]+(?:\w+[\s-]+){0,4}shares?|/\s*share|each[\s-]+(?:\w+[\s-]+){0,4}shares?",
    re.IGNORECASE,
)
# A final "price" under this, on a stock-consideration proposal, is
# almost certainly an exchange ratio (e.g. 0.3575 Axcelis shares per
# Veeco share) rather than a dollar amount -- no real public company's
# per-share deal price is genuinely this small. Using it as the ratio
# check's denominator would wrongly flag a genuine earlier cash price
# as implausible (seen live: Axcelis/Veeco's real $10.15/share cash
# component compared against a later 0.3575 exchange ratio, a bogus
# 28x "ratio").
MIN_RELIABLE_STOCK_FINAL_PRICE = 1.0


def _quotes_mention_aggregate_value(source_quotes) -> bool:
    """True only when a quote mentions an aggregate figure ("$47.5
    million") with NO "per share" qualifier anywhere in it. A quote
    that mentions both ("Implied TEV of $1,229 million; $29.50 per
    share") is normal and correct -- the extracted price corresponds
    to the per-share figure, the million/billion mention is just
    surrounding context -- and must NOT be treated as evidence the
    price itself is an aggregate value. This distinction is the whole
    difference between a real catch (Werewolf Therapeutics: "Werewolf's
    valuation would never fall below $5.5 million", no per-share
    figure anywhere) and a dangerous false positive (AVEO: "$500
    million (or an implied $13.51 per share)", where blindly
    reclassifying would have destroyed a correct $13.51/share price)."""
    quotes = [q or "" for q in (source_quotes or [])]
    has_million_billion = any(_MILLION_BILLION_RE.search(q) for q in quotes)
    has_per_share = any(_PER_SHARE_RE.search(q) for q in quotes)
    return has_million_billion and not has_per_share


def _is_implausible_per_share(value: float, final_price: float | None, quotes_mention_aggregate: bool) -> bool:
    if quotes_mention_aggregate:
        return True
    if value > ABSOLUTE_THRESHOLD_USD:
        return True
    if final_price is not None and final_price > 0 and value > RATIO_THRESHOLD * final_price:
        return True
    return False


def _deal_final_price(conn: psycopg.Connection, deal_id: str) -> float | None:
    rows = conn.execute(
        """
        SELECT p.date_resolved, p.price_low, p.price_high, p.status, p.consideration_type
        FROM proposals p JOIN extraction_runs r ON r.id = p.run_id
        WHERE r.deal_id = %s AND p.passed
        """,
        (deal_id,),
    ).fetchall()
    proposals = [
        {"date_resolved": r[0], "price_low": float(r[1]) if r[1] is not None else None,
         "price_high": float(r[2]) if r[2] is not None else None, "status": r[3], "consideration_type": r[4]}
        for r in rows
    ]
    dated = _dated_proposals(proposals)
    final = _final_entry(dated)
    if final is None:
        return None
    price = _price(final)
    if price is not None and final["consideration_type"] == "stock" and 0 < price < MIN_RELIABLE_STOCK_FINAL_PRICE:
        return None
    return price


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
                SELECT p.id, p.date_text, p.proposer, p.recipient, p.price_low, p.price_high, p.source_quotes
                FROM proposals p JOIN extraction_runs r ON r.id = p.run_id
                WHERE r.deal_id = %s AND (p.price_low IS NOT NULL OR p.price_high IS NOT NULL)
                """,
                (deal_id,),
            ).fetchall()

            for proposal_id, date_text, proposer, recipient, price_low, price_high, source_quotes in proposals:
                price_low = float(price_low) if price_low is not None else None
                price_high = float(price_high) if price_high is not None else None
                quotes_mention_aggregate = _quotes_mention_aggregate_value(source_quotes)

                new_price_low, new_total_low = price_low, None
                new_price_high, new_total_high = price_high, None
                moved_this = False

                if price_low is not None and _is_implausible_per_share(price_low, final_price, quotes_mention_aggregate):
                    new_price_low, new_total_low = None, price_low
                    moved_this = True
                if price_high is not None and _is_implausible_per_share(price_high, final_price, quotes_mention_aggregate):
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
