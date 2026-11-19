"""Generates an evidence packet for the same 20-deal sample as
src.bulk_sample (same seed, same deals), pairing each extracted
deal_metrics field with the literal filing text that backs it, so a
human reviewer can check correctness without re-deriving anything
themselves.

    python -m src.spotcheck_packet

No verdicts, no "looks correct" notes -- just extracted value, exact
quote, a direct SEC link, and a blank checkbox per field.

Bulk deals' paragraph text was never persisted to the `paragraphs`
table (that table only holds the original hand-curated deals) -- it's
re-derived here from the same cached filing HTML and the same
src.sections.extract_sections logic that src.load_bulk used when it
first built each event/proposal's source_paragraph_ids, so paragraph
IDs line up exactly. src.load_bulk only ever extracts the
"background_of_the_merger" section, so that's the only section name
that appears here.
"""

from pathlib import Path

import psycopg

from src.bulk_sample import SEED, N_SAMPLE, _parse_slug, filing_link
from src.bulk_stats import (
    _add_bidder,
    _is_non_bidder_role,
    _latest_signing_date,
    _PARTIAL_PROPOSAL_RE,
    _process_start_date,
    _resolve_target,
    _split_joint_proposer,
)
from src.bulk_run import load_cached_html
from src.env import load_env
from src.load_db import connect
from src import sections as sections_module

load_env()

OUTPUT_PATH = Path("data/output/spotcheck_packet.md")
SECTION_DISPLAY_NAME = "Background of the Merger"

FIELDS = [
    "Acquirer",
    "Signing date",
    "Final price",
    "Number of bidders",
    "First contact date",
]


def _paragraph_lookup(slug: str) -> dict[str, str]:
    cik, accession_nodash = _parse_slug(slug)
    accession = f"{accession_nodash[:10]}-{accession_nodash[10:12]}-{accession_nodash[12:18]}"
    html = load_cached_html(cik, accession)
    if not html:
        return {}
    found = sections_module.extract_sections(html)
    section = found.get("background_of_the_merger")
    return {p["id"]: p["text"] for p in section["paragraphs"]} if section else {}


def _fetch_events(conn: psycopg.Connection, deal_id: str, target: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT date_text, date_start, event_type, parties, source_paragraph_ids, source_quotes
        FROM events e JOIN extraction_runs r ON r.id = e.run_id
        WHERE r.deal_id = %s AND e.passed
        ORDER BY date_start NULLS LAST
        """,
        (deal_id,),
    ).fetchall()
    return [
        {
            "date_text": r[0], "date_start": r[1], "event_type": r[2],
            "parties": [_resolve_target(p, target) for p in (r[3] or [])],
            "source_paragraph_ids": r[4] or [], "source_quotes": r[5] or [],
        }
        for r in rows
    ]


def _fetch_proposals(conn: psycopg.Connection, deal_id: str, target: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT date_text, date_resolved, proposer, recipient, price_low, price_high,
               currency, consideration_type, status, source_paragraph_ids, source_quotes
        FROM proposals p JOIN extraction_runs r ON r.id = p.run_id
        WHERE r.deal_id = %s AND p.passed
        ORDER BY date_resolved NULLS LAST
        """,
        (deal_id,),
    ).fetchall()
    return [
        {
            "date_text": r[0], "date_resolved": r[1],
            "proposer": _resolve_target(r[2], target), "recipient": _resolve_target(r[3], target),
            "price_low": r[4], "price_high": r[5], "currency": r[6],
            "consideration_type": r[7], "status": r[8],
            "source_paragraph_ids": r[9] or [], "source_quotes": r[10] or [],
        }
        for r in rows
    ]


def _fetch_metrics(conn: psycopg.Connection, deal_id: str) -> dict:
    row = conn.execute(
        """
        SELECT target_display, acquirer_display, final_price, n_bidders
        FROM deal_metrics WHERE deal_id = %s
        """,
        (deal_id,),
    ).fetchone()
    keys = ["target_display", "acquirer_display", "final_price", "n_bidders"]
    return dict(zip(keys, row))


def _quote_block(paragraphs: dict[str, str], paragraph_ids: list[str], fallback_quotes: list[str]) -> tuple[str, str]:
    """Returns (quote_text, paragraph_id_label). Prefers the full stored
    paragraph text (re-derived, see module docstring); falls back to the
    extraction's own source_quotes if the paragraph id didn't resolve."""
    for pid in paragraph_ids:
        if pid in paragraphs:
            return paragraphs[pid], pid
    if fallback_quotes:
        return fallback_quotes[0], "(paragraph id unresolved)"
    return "(no source quote recorded)", "(none)"


def _checkbox(label: str) -> str:
    return f"- [ ] {label} correct"


def render_deal(conn: psycopg.Connection, deal_id: str, slug: str, target: str) -> str:
    link = filing_link(*_parse_slug(slug))
    paragraphs = _paragraph_lookup(slug)
    events = _fetch_events(conn, deal_id, target)
    proposals = _fetch_proposals(conn, deal_id, target)
    metrics = _fetch_metrics(conn, deal_id)

    lines = [
        f"## {metrics['target_display']} <- {metrics['acquirer_display']}",
        "",
        f"- Filing: {link}",
        f"- Section: {SECTION_DISPLAY_NAME}",
        "",
    ]

    # --- Acquirer + Final price: both read off the accepted proposal ---
    accepted = next((p for p in proposals if p["status"] == "accepted"), None)
    lines.append("### Acquirer")
    lines.append(f"- Extracted value: {metrics['acquirer_display']}")
    if accepted:
        quote, pid = _quote_block(paragraphs, accepted["source_paragraph_ids"], accepted["source_quotes"])
        lines.append(f"- Quote ({pid}): \"{quote}\"")
    else:
        signing = next((e for e in events if e["event_type"] == "signing"), None)
        if signing:
            quote, pid = _quote_block(paragraphs, signing["source_paragraph_ids"], signing["source_quotes"])
            lines.append(f"- Quote ({pid}, from signing event -- no accepted proposal recorded): \"{quote}\"")
        else:
            lines.append("- Quote: (no accepted proposal or signing event recorded)")
    lines.append(_checkbox("Acquirer"))
    lines.append("")

    lines.append("### Signing date")
    signing_date = _latest_signing_date({"events": events})
    lines.append(f"- Extracted value: {signing_date}")
    signing_events = [e for e in events if e["event_type"] == "signing" and e["date_start"] == signing_date]
    if signing_events:
        quote, pid = _quote_block(paragraphs, signing_events[0]["source_paragraph_ids"], signing_events[0]["source_quotes"])
        lines.append(f"- Quote ({pid}): \"{quote}\"")
    else:
        lines.append("- Quote: (no signing event recorded)")
    lines.append(_checkbox("Signing date"))
    lines.append("")

    lines.append("### Final price")
    if accepted:
        price = (
            f"{accepted['price_low']}"
            if accepted["price_low"] == accepted["price_high"]
            else f"{accepted['price_low']}-{accepted['price_high']}"
        )
        lines.append(
            f"- Extracted value: {metrics['final_price']} "
            f"({price} {accepted['currency'] or ''} [{accepted['consideration_type']}])".replace("  ", " ")
        )
    else:
        lines.append(f"- Extracted value: {metrics['final_price']}")
    if accepted:
        quote, pid = _quote_block(paragraphs, accepted["source_paragraph_ids"], accepted["source_quotes"])
        lines.append(f"- Quote ({pid}): \"{quote}\"")
    else:
        lines.append("- Quote: (no accepted proposal recorded)")
    lines.append(_checkbox("Final price"))
    lines.append("")

    lines.append("### Number of bidders")
    lines.append(f"- Extracted value: {metrics['n_bidders']}")
    # Mirrors src.bulk_stats.compute_n_bidders_for_deal exactly (joint
    # -bid splitting, governance-body and partial-proposal exclusion,
    # same-entity merging), so the evidence list below always matches
    # metrics['n_bidders'] itself -- a naive one-proposer-string-per-row
    # count would show a different number of names than the count it's
    # meant to support.
    bidder_names: set[str] = set()
    bidders: dict[str, dict] = {}
    for p in proposals:
        proposer = p.get("proposer")
        if not proposer or proposer == target or _is_non_bidder_role(proposer):
            continue
        if _PARTIAL_PROPOSAL_RE.search(" ".join(p.get("source_quotes") or [])):
            continue
        for name in _split_joint_proposer(proposer):
            if name == target or _is_non_bidder_role(name):
                continue
            before = set(bidder_names)
            _add_bidder(bidder_names, name)
            if bidder_names != before:
                bidders[name] = p
    lines.append("- Evidence (one proposal per distinct bidder named above the count):")
    for name in sorted(bidders):
        quote, pid = _quote_block(paragraphs, bidders[name]["source_paragraph_ids"], bidders[name]["source_quotes"])
        lines.append(f"  - **{name}** ({pid}): \"{quote}\"")
    lines.append(_checkbox("Number of bidders"))
    lines.append("")

    lines.append("### First contact date")
    # No earliest-dated-event fallback -- see src.bulk_stats._process_start_date;
    # a deal with no extracted first_contact event shows None here,
    # matching what's actually stored in deal_metrics/excluded from
    # timing stats, rather than guessing from an unrelated event type.
    process_start = _process_start_date({"events": events})
    lines.append(f"- Extracted value: {process_start}")
    fc_events = [e for e in events if e["event_type"] == "first_contact" and e["date_start"] == process_start]
    if process_start is not None and fc_events:
        quote, pid = _quote_block(paragraphs, fc_events[0]["source_paragraph_ids"], fc_events[0]["source_quotes"])
        lines.append(f"- Quote ({pid}): \"{quote}\"")
    else:
        lines.append("- Quote: (no first_contact event recorded)")
    lines.append(_checkbox("First contact date"))
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT d.id, d.slug, d.target
            FROM deals d JOIN deal_metrics dm ON dm.deal_id = d.id
            WHERE d.slug LIKE 'bulk_%' AND d.is_canonical AND NOT dm.excluded_from_stats
            ORDER BY d.slug
            """
        ).fetchall()

        import random
        rng = random.Random(SEED)
        sample = rng.sample(rows, min(N_SAMPLE, len(rows)))

        sections = [render_deal(conn, deal_id, slug, target) for deal_id, slug, target in sample]

    header = (
        f"# Spot-check evidence packet\n\n"
        f"Same {len(sample)}-deal sample as data/output/bulk_sample_spotcheck.md "
        f"(seed={SEED}). For each of the 5 extracted fields below, the quote is the "
        f"stored filing paragraph (re-derived from the cached filing HTML via the "
        f"same section-split logic the pipeline used when it first extracted these "
        f"records, since bulk deals' paragraph text isn't persisted to Postgres) -- "
        f"not an LLM paraphrase. No verdicts are given here; check each box yourself.\n\n"
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(header + "\n".join(sections))
    print(f"wrote {OUTPUT_PATH} ({len(sample)} deals)")


if __name__ == "__main__":
    main()
