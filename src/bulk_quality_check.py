"""Pilot quality check: run the pure, no-LLM validate/sanity layer against
already-extracted bulk pilot results (data/output/bulk_runs/*.json).

    python -m src.bulk_quality_check

Re-derives each candidate's background-section paragraphs from the same
cached document the extraction read (no network, no LLM), so
check_quotes_in_paragraphs can verify every source_quote actually appears
verbatim -- exactly the quote-match rate this is meant to surface.

Bulk candidates have no registered acquirer name (unlike the hand-curated
DEALS registry), so the signing-event sanity check needs a heuristic
guess: the most common non-target name across proposer/recipient. This
is a best-effort input to a diagnostic report, not something fed back
into the pipeline's own data.
"""

import glob
import json
from collections import Counter
from pathlib import Path
from typing import Optional

from src import sanity, sections, validate
from src.bulk_run import BULK_OUTPUT_DIR, load_cached_html
from src.entity_match import is_same_entity


def _resolve_target_placeholder(name: Optional[str], target_name: str) -> Optional[str]:
    """Bulk pilot results skip validate.run()'s normalize_defined_terms
    entirely (that's a later-pass step, not extraction) -- but without
    it, "Company"/"Board"/etc. placeholders are still literal, which
    would make guess_acquirer below pick "Company" as the most common
    non-target name instead of the real acquirer. Resolves the TARGET
    side (the one name we actually know here) via both its defined-term
    placeholders AND is_same_entity, since an informal short name
    ("Knoll") used as proposer/recipient text doesn't equal the raw
    EDGAR legal name ("KNOLL INC") under exact string comparison --
    that near-miss previously let the target's own short name slip
    through uncounted as a candidate "acquirer". Acquirer-side
    placeholders (Parent, Merger Sub, Buyer) are deliberately left
    as-is -- they're informative as "unresolved" rather than disappearing
    into a guessed value.
    """
    if name and (name.strip().lower() in validate._TARGET_DEFINED_TERMS or is_same_entity(name, target_name)):
        return target_name
    return name


def guess_acquirer(target_name: str, proposals: list[dict]) -> Optional[str]:
    counts = Counter()
    for p in proposals:
        for raw_name in (p.get("proposer"), p.get("recipient")):
            name = _resolve_target_placeholder(raw_name, target_name)
            if name and name != target_name:
                counts[name] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def check_one(result: dict) -> dict:
    row = result["row"]
    target_name = row["target_name"]
    html = load_cached_html(row["target_cik"], row["primary_accession"])
    if html is None:
        return {"target_name": target_name, "error": "cached document missing"}

    found = sections.extract_sections(html)
    section = found.get("background_of_the_merger")
    paragraph_lookup = {p["id"]: p["text"] for p in section["paragraphs"]} if section else {}

    records_by_type = {"Event": result["events"], "Proposal": result["proposals"], "ValuationAnalysis": []}
    validated = validate.validate_all(records_by_type, paragraph_lookup)

    n_total = len(validated)
    n_passed = sum(1 for r in validated if r["passed"])
    n_quote_match = sum(1 for r in validated if r["checks"].get("quotes_in_paragraphs"))
    failure_reasons = sorted({reason for r in validated for reason in r["failure_reasons"]})

    acquirer_guess = guess_acquirer(target_name, result["proposals"])

    # Same target-side-only resolution for the sanity input: check_signing_
    # event_exists substring-matches target_name against Event.parties, so
    # a literal "Company"/"Board" there would make the check fail even
    # when the real target IS named via its placeholder.
    resolved_events = [
        {**e, "parties": [_resolve_target_placeholder(p, target_name) for p in e.get("parties", [])]}
        for e in result["events"]
    ]
    resolved_proposals = [
        {
            **p,
            "proposer": _resolve_target_placeholder(p.get("proposer"), target_name),
            "recipient": _resolve_target_placeholder(p.get("recipient"), target_name),
        }
        for p in result["proposals"]
    ]
    sanity_input = {"Event": resolved_events, "Proposal": resolved_proposals, "ValuationAnalysis": []}
    sanity_results = sanity.run(sanity_input, html, target_name, acquirer_guess or "")

    return {
        "target_name": target_name,
        "form_type": row["primary_form_type"],
        "n_events": len(result["events"]),
        "n_proposals": len(result["proposals"]),
        "validation_pass_rate": n_passed / n_total if n_total else None,
        "quote_match_rate": n_quote_match / n_total if n_total else None,
        "validation_failure_reasons": failure_reasons,
        "acquirer_guess": acquirer_guess,
        "sanity": {r["name"]: {"passed": r["passed"], "detail": r["detail"]} for r in sanity_results},
    }


def main() -> None:
    reports = []
    for path in sorted(glob.glob(str(BULK_OUTPUT_DIR / "*.json"))):
        result = json.loads(Path(path).read_text())
        if result.get("status") != "done":
            continue
        reports.append(check_one(result))

    print(json.dumps(reports, indent=2, default=str))


if __name__ == "__main__":
    main()
