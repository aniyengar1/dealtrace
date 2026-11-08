"""Score an extraction output against a hand-checked gold answer key.

    python -m src.score data/output/splunk_extraction.json data/benchmark/splunk_gold.json

Events are matched by (event_type, date) -- "date" means the extracted
event's date falls within the gold event's own date_precision window (a
"month" or "range" gold entry is a tolerant window; "day" requires an exact
match). Proposals are matched by (date, price_low, price_high). Both are
one-to-one greedy matches: a gold item can match at most one extracted item
and vice versa, so recall/precision can't double-count.

proposer/recipient accuracy maps older extractions' anonymized "Party A"/
"Party B" labels back to this deal's real target/acquirer names (see
PARTY_NAME_MAP) before comparing against gold, since gold always uses real
names and only pre-v5 prompts anonymized.
"""

import argparse
import calendar
import json
from datetime import date as date_cls
from pathlib import Path
from typing import Optional

from src.validate import _try_parse_date

NUMBER_TOLERANCE = 0.01

# src/run.py's DEALS["splunk"] fixes the target as Splunk and the acquirer as
# Cisco; extractions made before the v5 prompt anonymized them as Party A/B
# (src/extract.py's old target_label/acquirer_label convention). Gold always
# uses real names, so older extractions need this map to compare at all.
PARTY_NAME_MAP = {
    "Party A": "Splunk",
    "Party B": "Cisco",
}


def normalize_party(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    return PARTY_NAME_MAP.get(name, name)


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


def match_events(gold_events: list[dict], extracted_events: list[dict]) -> dict:
    """Greedily one-to-one match gold events to extracted events."""
    unmatched = list(range(len(extracted_events)))
    matches: list[tuple[dict, dict]] = []
    misses: list[dict] = []

    for gold in gold_events:
        g_range = gold_event_date_range(gold)
        found_idx = None
        for idx in unmatched:
            rec = extracted_events[idx]
            if rec.get("event_type") != gold["event_type"]:
                continue
            e_range = extracted_event_date_range(rec)
            if e_range is None or not _ranges_overlap(g_range, e_range):
                continue
            found_idx = idx
            break
        if found_idx is not None:
            matches.append((gold, extracted_events[found_idx]))
            unmatched.remove(found_idx)
        else:
            misses.append(gold)

    extras = [extracted_events[i] for i in unmatched]
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
            e_date = _try_parse_date(rec.get("date", ""))
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


def score_extraction(gold: dict, extraction: dict[str, list[dict]]) -> dict:
    """Score one extraction's Events and Proposals against gold. No I/O."""
    gold_events = gold.get("events", [])
    extracted_events = extraction.get("Event", [])
    event_result = match_events(gold_events, extracted_events)

    core_gold_events = [g for g in gold_events if g.get("core")]
    core_misses = [g for g in event_result["misses"] if g.get("core")]
    core_matched = len(core_gold_events) - len(core_misses)

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
        if normalize_party(rec.get("proposer")) == g.get("proposer")
        and normalize_party(rec.get("recipient")) == g.get("recipient")
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
