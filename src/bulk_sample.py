"""Generates a fixed-seed random sample of canonical, post-fix bulk
deals as a markdown file for manual accuracy spot-checking against the
real filings, with a fillable checklist per deal.

    python -m src.bulk_sample

Scoped to canonical BULK deals (is_canonical AND slug LIKE 'bulk_%'),
further restricted to deal_metrics.excluded_from_stats = false -- a
spin-off, affiliated-manager merger, or filer/target reversal
(src.classify_deal_type) isn't a representative ordinary sale process
to spot-check, and the reversed ones would have swapped target/
acquirer labels that make the rendered checklist nonsensical to review
in the first place. Curated deals are excluded since they're already
hand-reviewed and don't have a bulk-style slug to derive an EDGAR
filing link from, and a duplicate bulk row that lost to another
canonical row shouldn't be spot-checked as if it were representative.

CIK and accession number are recovered by parsing them back out of the
deal's own slug (minted by src.load_bulk.bulk_slug as
"bulk_{cik}_{accession_nodash}") rather than from a separate stored
column -- accession numbers are always exactly 18 digits (10+2+6), so
re-inserting the dashes is unambiguous.

The "as loaded" reference block (acquirer, final price, bidder counts)
reads directly from deal_metrics -- the same single source of truth
the website reads -- rather than recomputing independently, so this
file can never show something different from what deal_metrics
actually holds.
"""

import random
from pathlib import Path

import psycopg

from src.bulk_stats import (
    _add_bidder,
    _is_non_bidder_role,
    _is_same_company_fuzzy,
    _is_unusable_fragment,
    _latest_signing_date,
    _PARTIAL_PROPOSAL_RE,
    _resolve_target,
    _split_joint_proposer,
)
from src.env import load_env
from src.load_db import connect

load_env()

SEED = 2028
N_SAMPLE = 20
OUTPUT_PATH = Path("data/output/bulk_sample_spotcheck.md")

CHECKLIST_ITEMS = [
    "Acquirer correct?",
    "Signing date correct?",
    "Final price correct?",
    "# bidders plausible?",
    "Any wrong/missing major event?",
]


def _accession_with_dashes(accession_nodash: str) -> str:
    return f"{accession_nodash[:10]}-{accession_nodash[10:12]}-{accession_nodash[12:18]}"


def _parse_slug(slug: str) -> tuple[str, str]:
    # "bulk_{cik}_{accession_nodash}"
    _, cik, accession_nodash = slug.split("_")
    return cik, accession_nodash


def filing_link(cik: str, accession_nodash: str) -> str:
    accession_dashed = _accession_with_dashes(accession_nodash)
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_nodash}/{accession_dashed}-index.htm"


def _fetch_timeline(conn: psycopg.Connection, deal_id: str, target: str) -> tuple[list[dict], list[dict]]:
    events = conn.execute(
        """
        SELECT date_text, date_start, event_type, parties, summary
        FROM events e JOIN extraction_runs r ON r.id = e.run_id
        WHERE r.deal_id = %s AND e.passed
        ORDER BY date_start NULLS LAST
        """,
        (deal_id,),
    ).fetchall()
    proposals = conn.execute(
        """
        SELECT date_text, date_resolved, proposer, recipient, price_low, price_high,
               currency, consideration_type, status, source_quotes
        FROM proposals p JOIN extraction_runs r ON r.id = p.run_id
        WHERE r.deal_id = %s AND p.passed
        ORDER BY date_resolved NULLS LAST
        """,
        (deal_id,),
    ).fetchall()
    return (
        [
            {
                "date": e[0], "date_start": e[1], "event_type": e[2],
                "parties": [_resolve_target(p, target) for p in (e[3] or [])],
                "summary": e[4],
            }
            for e in events
        ],
        [
            {
                "date": p[0], "date_resolved": p[1],
                "proposer": _resolve_target(p[2], target), "recipient": _resolve_target(p[3], target),
                "price_low": p[4], "price_high": p[5], "currency": p[6],
                "consideration_type": p[7], "status": p[8], "source_quotes": p[9] or [],
            }
            for p in proposals
        ],
    )


def render_deal(slug: str, target: str, acquirer: str, metrics: dict, events: list[dict], proposals: list[dict]) -> str:
    cik, accession_nodash = _parse_slug(slug)
    link = filing_link(cik, accession_nodash)
    lines = [f"## {metrics['target_display']} <- {metrics['acquirer_display']}", "", f"- Filing: {link}", ""]

    lines.append("### Events")
    if events:
        for e in events:
            parties = ", ".join(e["parties"] or [])
            lines.append(f"- **{e['date']}** [{e['event_type']}] {e['summary']} (parties: {parties})")
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

    signing_date = _latest_signing_date({"events": events})
    # Mirrors src.bulk_stats.compute_n_bidders_for_deal exactly (same
    # helpers, same exemption for the deal's own eventual acquirer), so
    # this parenthetical name list always matches metrics['n_bidders']
    # itself rather than a naive recount that could show a different
    # number of names than the count it's meant to support.
    bidders: set[str] = set()
    for p in proposals:
        proposer = p.get("proposer")
        if not proposer or _is_same_company_fuzzy(proposer, target) or _is_unusable_fragment(proposer):
            continue
        is_eventual_acquirer = _is_same_company_fuzzy(proposer, acquirer)
        if _is_non_bidder_role(proposer) and not is_eventual_acquirer:
            continue
        if _PARTIAL_PROPOSAL_RE.search(" ".join(p.get("source_quotes") or [])):
            continue
        for name in _split_joint_proposer(proposer):
            if _is_same_company_fuzzy(name, target) or _is_unusable_fragment(name):
                continue
            if _is_non_bidder_role(name) and not is_eventual_acquirer:
                continue
            _add_bidder(bidders, name)

    lines.append("### deal_metrics (reference for the checklist below -- single source of truth, not recomputed here)")
    lines.append(f"- Acquirer (acquirer_display): {metrics['acquirer_display']}")
    lines.append(f"- Signing date (as loaded): {signing_date}")
    lines.append(f"- Final price (final_price): {metrics['final_price']}  (price_plausible: {metrics['price_plausible']})")
    lines.append(f"- # bidders (n_bidders): {metrics['n_bidders']}  ({', '.join(sorted(bidders)) or 'none'})")
    lines.append(f"- # parties contacted (n_parties_contacted): {metrics['n_parties_contacted']}")
    lines.append(f"- # proposals (n_proposals): {metrics['n_proposals']}")
    lines.append("")

    lines.append("### Spot-check checklist")
    for item in CHECKLIST_ITEMS:
        lines.append(f"- {item} (Y/N): ____  Note: ____")
    lines.append("")
    return "\n".join(lines)


def _fetch_metrics(conn: psycopg.Connection, deal_id: str) -> dict:
    row = conn.execute(
        """
        SELECT target_display, acquirer_display, final_price, price_plausible,
               n_bidders, n_parties_contacted, n_proposals
        FROM deal_metrics WHERE deal_id = %s
        """,
        (deal_id,),
    ).fetchone()
    keys = ["target_display", "acquirer_display", "final_price", "price_plausible", "n_bidders", "n_parties_contacted", "n_proposals"]
    return dict(zip(keys, row))


def main() -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.slug, d.target, d.acquirer
            FROM deals d JOIN deal_metrics dm ON dm.deal_id = d.id
            WHERE d.slug LIKE 'bulk_%' AND d.is_canonical AND NOT dm.excluded_from_stats
            ORDER BY d.slug
            """
        ).fetchall()

        rng = random.Random(SEED)
        sample = rng.sample(rows, min(N_SAMPLE, len(rows)))

        sections = []
        for deal_id, slug, target, acquirer in sample:
            events, proposals = _fetch_timeline(conn, deal_id, target)
            metrics = _fetch_metrics(conn, deal_id)
            sections.append(render_deal(slug, target, acquirer, metrics, events, proposals))

    header = (
        f"# Bulk deal sample for manual spot-check\n\n"
        f"Random sample of {len(sample)} deals out of {len(rows)} canonical bulk deals "
        f"(curated deals, non-canonical duplicates, and deal_metrics.excluded_from_stats deals "
        f"-- spin-offs, affiliated-manager mergers, filer/target reversals -- excluded), seed={SEED} "
        f"(Python `random.Random({SEED}).sample(...)` over the cleaned canonical bulk deal set, sorted by slug).\n\n"
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(header + "\n".join(sections))
    print(f"wrote {OUTPUT_PATH} ({len(sample)} deals sampled from {len(rows)})")


if __name__ == "__main__":
    main()
