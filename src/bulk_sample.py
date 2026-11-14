"""Generates a fixed-seed random sample of loaded bulk deals as a
markdown file for manual accuracy spot-checking against the real
filings.

    python -m src.bulk_sample

CIK and accession number are recovered by parsing them back out of the
deal's own slug (minted by src.load_bulk.bulk_slug as
"bulk_{cik}_{accession_nodash}") rather than from a separate stored
column -- accession numbers are always exactly 18 digits (10+2+6), so
re-inserting the dashes is unambiguous.
"""

import random
from pathlib import Path

import psycopg

from src.env import load_env
from src.load_db import connect

load_env()

SEED = 42
N_SAMPLE = 20
OUTPUT_PATH = Path("data/output/bulk_sample_spotcheck.md")


def _accession_with_dashes(accession_nodash: str) -> str:
    return f"{accession_nodash[:10]}-{accession_nodash[10:12]}-{accession_nodash[12:18]}"


def _parse_slug(slug: str) -> tuple[str, str]:
    # "bulk_{cik}_{accession_nodash}"
    _, cik, accession_nodash = slug.split("_")
    return cik, accession_nodash


def filing_link(cik: str, accession_nodash: str) -> str:
    accession_dashed = _accession_with_dashes(accession_nodash)
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{accession_dashed}-index.htm"


def _fetch_timeline(conn: psycopg.Connection, deal_id: str) -> tuple[list[dict], list[dict]]:
    events = conn.execute(
        """
        SELECT date_text, event_type, parties, summary
        FROM events e JOIN extraction_runs r ON r.id = e.run_id
        WHERE r.deal_id = %s AND e.passed
        ORDER BY date_start NULLS LAST
        """,
        (deal_id,),
    ).fetchall()
    proposals = conn.execute(
        """
        SELECT date_text, proposer, recipient, price_low, price_high, currency, consideration_type, status
        FROM proposals p JOIN extraction_runs r ON r.id = p.run_id
        WHERE r.deal_id = %s AND p.passed
        ORDER BY date_resolved NULLS LAST
        """,
        (deal_id,),
    ).fetchall()
    return (
        [{"date": e[0], "type": e[1], "parties": e[2], "summary": e[3]} for e in events],
        [
            {
                "date": p[0], "proposer": p[1], "recipient": p[2],
                "price_low": p[3], "price_high": p[4], "currency": p[5],
                "consideration_type": p[6], "status": p[7],
            }
            for p in proposals
        ],
    )


def render_deal(slug: str, deal_name: str, target: str, events: list[dict], proposals: list[dict]) -> str:
    cik, accession_nodash = _parse_slug(slug)
    link = filing_link(cik, accession_nodash)
    lines = [f"## {deal_name}", "", f"- Target: {target}", f"- Filing: {link}", ""]

    lines.append("### Events")
    if events:
        for e in events:
            parties = ", ".join(e["parties"] or [])
            lines.append(f"- **{e['date']}** [{e['type']}] {e['summary']} (parties: {parties})")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("### Proposals")
    if proposals:
        for p in proposals:
            price = f"{p['price_low']}" if p["price_low"] == p["price_high"] else f"{p['price_low']}-{p['price_high']}"
            lines.append(
                f"- **{p['date']}** {p['proposer']} -> {p['recipient']}: "
                f"{price} {p['currency'] or ''} ({p['consideration_type']}, {p['status']})"
            )
    else:
        lines.append("- (none)")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, slug, deal_name, target FROM deals WHERE slug LIKE 'bulk_%' ORDER BY slug"
        ).fetchall()

        rng = random.Random(SEED)
        sample = rng.sample(rows, min(N_SAMPLE, len(rows)))

        sections = []
        for deal_id, slug, deal_name, target in sample:
            events, proposals = _fetch_timeline(conn, deal_id)
            sections.append(render_deal(slug, deal_name, target, events, proposals))

    header = (
        f"# Bulk deal sample for manual spot-check\n\n"
        f"Random sample of {len(sample)} deals out of {len(rows)} loaded bulk deals, "
        f"seed={SEED} (Python `random.Random({SEED}).sample(...)` over deals sorted by slug).\n\n"
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(header + "\n".join(sections))
    print(f"wrote {OUTPUT_PATH} ({len(sample)} deals sampled from {len(rows)})")


if __name__ == "__main__":
    main()
