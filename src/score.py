"""Score an extraction output against a hand-checked gold answer key.

    python -m src.score data/output/splunk_extraction.json data/benchmark/splunk_gold.json

Events are matched on date alone (respecting the gold entry's own
date_precision -- a "month" or "range" gold entry is a tolerant window,
"day" requires exact equality) plus a content signal: either the gold
entry's own paragraph_id appears in the extracted event's
source_paragraph_ids, or the two summaries have "strong" overlap (see
summary_overlap). event_type is NOT part of matching -- it's scored
separately, among matched pairs, the same way proposal_kind is.

Matching is global, not a naive per-gold-event greedy pass: every valid
(gold, extracted) pair is scored, pairs are ranked (same_paragraph outranks
any overlap-only pair, then by overlap), and assigned highest-score-first,
skipping either side once it's taken. This matters whenever one paragraph
supports multiple gold events (the task note that one paragraph can
contain multiple events) -- a per-gold-event-in-list-order greedy pass can
hand a shared paragraph's one extracted event to the first gold event that
asks for it even when a later gold event is the actual content match;
global assignment picks the best overall pairing instead.

Proposals are matched by (date, price_low, price_high), one-to-one greedy
(little ambiguity there -- price is close to a unique key).

proposer/recipient and event-parties comparisons are exact string matches
against gold's real names after case/whitespace normalization only. Older
(pre-v5) extractions anonymize parties as "Party A"/"Party B" and will
correctly score ~0 here -- that's not a bug, it's the anonymization
showing up as a real gap against gold's real names.
"""

import argparse
import calendar
import json
import re
from datetime import date as date_cls
from pathlib import Path
from typing import Optional

from src.validate import _try_parse_date

NUMBER_TOLERANCE = 0.01

# "Strong" overlap of the two summaries' content words, stemmed crudely (see
# _stems) so verb/noun form differences (engaged/engagement, withdrew/
# withdrawal) don't suppress an otherwise-matching pair. Calibrated against
# a manual count of the Splunk background section: this threshold recovers
# exactly the matches a human reader would call the same event and no
# others, on both the gemini-3-flash-preview and gemini-3.6-flash runs
# scored while building this module.
SUMMARY_OVERLAP_THRESHOLD = 0.3
_STEM_LEN = 6
_STOPWORDS = {
    "a", "an", "the", "to", "and", "or", "of", "in", "on", "with", "its",
    "for", "by", "at", "as", "is", "are", "was", "were", "be", "that",
    "this", "than", "from", "it", "their", "after", "during", "party",
    "parties",
}
_WORD_RE = re.compile(r"[a-z0-9]+")


def _stems(text: Optional[str]) -> set[str]:
    words = _WORD_RE.findall((text or "").lower())
    return {w[:_STEM_LEN] for w in words if w not in _STOPWORDS and len(w) > 2}


def summary_overlap(a: Optional[str], b: Optional[str]) -> float:
    """Overlap-coefficient similarity of two summaries' stemmed content words."""
    ta, tb = _stems(a), _stems(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def normalize_name(name: Optional[str]) -> Optional[str]:
    """Case/whitespace-only normalization -- NOT an anonymization bridge.

    "Cisco" vs "Party B" must stay unequal: anonymized output is a real gap
    against gold's real names, not a formatting difference to paper over.
    """
    if name is None:
        return None
    return " ".join(name.split()).lower()


def load_gold(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def load_extraction(path: Path) -> dict[str, list[dict]]:
    """Group a validate.py-style extraction file's records by record_type."""
    results = json.loads(Path(path).read_text())
    by_type: dict[str, list[dict]] = {"Event": [], "Proposal": [], "ValuationAnalysis": []}
    for r in results:
        by_type.setdefault(r["record_type"], []).append(r["record"])
    return by_type


def _parse_iso(text: str) -> date_cls:
    return date_cls.fromisoformat(text)


def gold_event_date_range(gold_event: dict) -> tuple[date_cls, date_cls]:
    """Expand a gold event's (date, date_precision) into an inclusive window."""
    precision = gold_event["date_precision"]
    raw = gold_event["date"]
    if precision == "range":
        start_s, end_s = raw.split("/")
        return _parse_iso(start_s), _parse_iso(end_s)
    if precision == "month":
        year, month = (int(p) for p in raw.split("-"))
        last_day = calendar.monthrange(year, month)[1]
        return date_cls(year, month, 1), date_cls(year, month, last_day)
    return _parse_iso(raw), _parse_iso(raw)  # "day"


def extracted_event_date_range(record: dict) -> Optional[tuple[date_cls, date_cls]]:
    """Expand an extracted Event's date_start/date_end into an inclusive window."""
    start = record.get("date_start")
    if start is None:
        return None
    end = record.get("date_end") or start
    return _parse_iso(start), _parse_iso(end)


def _ranges_overlap(a: tuple[date_cls, date_cls], b: tuple[date_cls, date_cls]) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def _numbers_close(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < NUMBER_TOLERANCE


def extracted_proposal_date(record: dict) -> Optional[date_cls]:
    """An extracted Proposal's effective date: date_resolved if the model
    (or the extractor's relative-date fallback) resolved a relative phrase
    like "later that day", else whatever _try_parse_date can get from the
    literal `date` text.
    """
    resolved = record.get("date_resolved")
    if resolved:
        return _parse_iso(resolved) if isinstance(resolved, str) else resolved
    return _try_parse_date(record.get("date", ""))


def match_events(gold_events: list[dict], extracted_events: list[dict]) -> dict:
    """Globally match gold events to extracted events (see module docstring)."""
    candidates: list[tuple[tuple[int, float], int, int]] = []
    for gi, gold in enumerate(gold_events):
        g_range = gold_event_date_range(gold)
        for ei, rec in enumerate(extracted_events):
            e_range = extracted_event_date_range(rec)
            if e_range is None or not _ranges_overlap(g_range, e_range):
                continue
            same_paragraph = gold.get("paragraph_id") in (rec.get("source_paragraph_ids") or [])
            overlap = summary_overlap(gold.get("summary"), rec.get("summary"))
            if same_paragraph or overlap >= SUMMARY_OVERLAP_THRESHOLD:
                candidates.append(((1 if same_paragraph else 0, overlap), gi, ei))

    candidates.sort(key=lambda c: c[0], reverse=True)
    matched_gold: set[int] = set()
    matched_extracted: set[int] = set()
    matches: list[tuple[dict, dict]] = []
    for _score, gi, ei in candidates:
        if gi in matched_gold or ei in matched_extracted:
            continue
        matched_gold.add(gi)
        matched_extracted.add(ei)
        matches.append((gold_events[gi], extracted_events[ei]))

    misses = [g for gi, g in enumerate(gold_events) if gi not in matched_gold]
    extras = [r for ei, r in enumerate(extracted_events) if ei not in matched_extracted]
    return {"matches": matches, "misses": misses, "extras": extras}


def match_proposals(gold_proposals: list[dict], extracted_proposals: list[dict]) -> dict:
    """Greedily one-to-one match gold proposals to extracted proposals."""
    unmatched = list(range(len(extracted_proposals)))
    matches: list[tuple[dict, dict]] = []
    misses: list[dict] = []

    for gold in gold_proposals:
        g_date = _parse_iso(gold["date"])
        found_idx = None
        for idx in unmatched:
            rec = extracted_proposals[idx]
            e_date = extracted_proposal_date(rec)
            if e_date != g_date:
                continue
            if not _numbers_close(rec.get("price_low"), gold.get("price_low")):
                continue
            if not _numbers_close(rec.get("price_high"), gold.get("price_high")):
                continue
            found_idx = idx
            break
        if found_idx is not None:
            matches.append((gold, extracted_proposals[found_idx]))
            unmatched.remove(found_idx)
        else:
            misses.append(gold)

    extras = [extracted_proposals[i] for i in unmatched]
    return {"matches": matches, "misses": misses, "extras": extras}


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    return numerator / denominator if denominator else None


def _event_parties_include_gold(gold: dict, rec: dict) -> bool:
    gold_names = {normalize_name(n) for n in gold.get("parties", [])}
    extracted_names = {normalize_name(n) for n in rec.get("parties", [])}
    return gold_names.issubset(extracted_names)


def score_extraction(gold: dict, extraction: dict[str, list[dict]]) -> dict:
    """Score one extraction's Events and Proposals against gold. No I/O."""
    gold_events = gold.get("events", [])
    extracted_events = extraction.get("Event", [])
    event_result = match_events(gold_events, extracted_events)

    core_gold_events = [g for g in gold_events if g.get("core")]
    core_misses = [g for g in event_result["misses"] if g.get("core")]
    core_matched = len(core_gold_events) - len(core_misses)

    event_type_correct = sum(
        1 for g, rec in event_result["matches"] if rec.get("event_type") == g.get("event_type")
    )
    event_parties_correct = sum(
        1 for g, rec in event_result["matches"] if _event_parties_include_gold(g, rec)
    )

    gold_proposals = gold.get("proposals", [])
    extracted_proposals = extraction.get("Proposal", [])
    proposal_result = match_proposals(gold_proposals, extracted_proposals)

    kind_correct = sum(
        1
        for g, rec in proposal_result["matches"]
        if rec.get("proposal_kind") == g.get("proposal_kind")
    )
    party_correct = sum(
        1
        for g, rec in proposal_result["matches"]
        if normalize_name(rec.get("proposer")) == normalize_name(g.get("proposer"))
        and normalize_name(rec.get("recipient")) == normalize_name(g.get("recipient"))
    )

    return {
        "events": {
            "n_gold": len(gold_events),
            "n_extracted": len(extracted_events),
            "n_matched": len(event_result["matches"]),
            "recall": _ratio(len(event_result["matches"]), len(gold_events)),
            "precision": _ratio(len(event_result["matches"]), len(extracted_events)),
            "core_n_gold": len(core_gold_events),
            "core_n_matched": core_matched,
            "core_recall": _ratio(core_matched, len(core_gold_events)),
            "event_type_correct": event_type_correct,
            "event_type_total": len(event_result["matches"]),
            "parties_correct": event_parties_correct,
            "parties_total": len(event_result["matches"]),
            "misses": event_result["misses"],
            "extras": event_result["extras"],
        },
        "proposals": {
            "n_gold": len(gold_proposals),
            "n_extracted": len(extracted_proposals),
            "n_matched": len(proposal_result["matches"]),
            "recall": _ratio(len(proposal_result["matches"]), len(gold_proposals)),
            "precision": _ratio(len(proposal_result["matches"]), len(extracted_proposals)),
            "proposal_kind_correct": kind_correct,
            "proposal_kind_total": len(proposal_result["matches"]),
            "proposer_recipient_correct": party_correct,
            "proposer_recipient_total": len(proposal_result["matches"]),
            "misses": proposal_result["misses"],
            "extras": proposal_result["extras"],
        },
    }


def _pct(ratio: Optional[float]) -> str:
    return "n/a" if ratio is None else f"{ratio:.0%}"


def format_report(result: dict) -> str:
    lines = []
    ev = result["events"]
    lines.append("=== Events ===")
    lines.append(f"Recall: {ev['n_matched']}/{ev['n_gold']} ({_pct(ev['recall'])})")
    lines.append(
        f"Core-only recall: {ev['core_n_matched']}/{ev['core_n_gold']} ({_pct(ev['core_recall'])})"
    )
    lines.append(f"Precision: {ev['n_matched']}/{ev['n_extracted']} ({_pct(ev['precision'])})")
    lines.append(
        f"event_type accuracy (of matched): {ev['event_type_correct']}/{ev['event_type_total']}"
    )
    lines.append(
        f"parties-include-gold-names accuracy (of matched): {ev['parties_correct']}/{ev['parties_total']}"
    )
    lines.append(f"\nMisses ({len(ev['misses'])}):")
    for g in ev["misses"]:
        core_tag = " [core]" if g.get("core") else ""
        lines.append(f"  - {g['id']} {g['date']} [{g['event_type']}]{core_tag}: {g['summary']}")
    lines.append(f"\nExtras ({len(ev['extras'])}):")
    for rec in ev["extras"]:
        lines.append(f"  - {rec.get('date_text')} [{rec.get('event_type')}]: {rec.get('summary')}")

    pr = result["proposals"]
    lines.append("\n=== Proposals ===")
    lines.append(f"Recall: {pr['n_matched']}/{pr['n_gold']} ({_pct(pr['recall'])})")
    lines.append(f"Precision: {pr['n_matched']}/{pr['n_extracted']} ({_pct(pr['precision'])})")
    lines.append(
        f"proposal_kind accuracy (of matched): {pr['proposal_kind_correct']}/{pr['proposal_kind_total']}"
    )
    lines.append(
        f"proposer/recipient accuracy (of matched): "
        f"{pr['proposer_recipient_correct']}/{pr['proposer_recipient_total']}"
    )
    lines.append(f"\nMisses ({len(pr['misses'])}):")
    for g in pr["misses"]:
        lines.append(
            f"  - {g['id']} {g['date']} {g['proposer']}->{g['recipient']} "
            f"${g['price_low']}-{g['price_high']} [{g['proposal_kind']}]"
        )
    lines.append(f"\nExtras ({len(pr['extras'])}):")
    for rec in pr["extras"]:
        lines.append(
            f"  - {rec.get('date')} {rec.get('proposer')}->{rec.get('recipient')} "
            f"${rec.get('price_low')}-{rec.get('price_high')} [{rec.get('proposal_kind')}]"
        )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Score an extraction file against a hand-checked gold answer key."
    )
    parser.add_argument("extraction_path", type=Path)
    parser.add_argument(
        "gold_path", type=Path, nargs="?", default=Path("data/benchmark/splunk_gold.json")
    )
    args = parser.parse_args()

    gold = load_gold(args.gold_path)
    extraction = load_extraction(args.extraction_path)
    result = score_extraction(gold, extraction)
    print(format_report(result))


if __name__ == "__main__":
    main()
