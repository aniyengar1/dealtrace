"""Validate extracted records against their source text and write outputs.

Every record must be traceable back to the filing: each of its 1-3
source_quotes has to appear verbatim (after normalization) in the paragraphs
it cites, every number it reports has to appear in at least one of those
quotes, low/high pairs have to be ordered correctly, and any dates have to
be internally consistent. Records that fail are kept (not dropped) but
flagged, so a human can see exactly what's unverified.
"""

import html as html_lib
import json
import re
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path

from src.schemas import Event, Proposal, ValuationAnalysis

DATA_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "output"
DATA_SECTIONS = Path(__file__).resolve().parent.parent / "data" / "sections"

_WHITESPACE_RE = re.compile(r"\s+")
# No leading sign: filing ranges are written "4.0x-6.0x" where the hyphen is
# a range separator, not a minus sign, and all price/multiple fields are
# positive magnitudes anyway.
_NUMBER_RE = re.compile(r"\d[\d,]*\.?\d*")

_LOW_HIGH_PAIRS = [
    ("price_low", "price_high"),
    ("multiple_low", "multiple_high"),
    ("implied_price_low", "implied_price_high"),
]

# Filing text and model output disagree on which Unicode code point to use
# for an otherwise-identical character (curly vs. straight quotes, en/em
# dash vs. hyphen, NBSP vs. regular space). None of that is a real content
# difference, so both sides of a quote match are folded onto one
# representative before comparing. Quotes fold all the way down to a
# single canonical character regardless of single/double or
# curly/straight style -- a model substituting a double quotation mark
# for a single one (or vice versa) around the same span is the same kind
# of non-content noise as a curly-vs-straight mismatch, not a real
# wording difference.
_QUOTE_NORMALIZE_MAP = str.maketrans(
    {
        "'": "'",  # straight single quote / apostrophe (canonical form)
        '"': "'",  # straight double quote
        "‘": "'",  # left single quotation mark
        "’": "'",  # right single quotation mark
        "‚": "'",  # single low-9 quotation mark
        "′": "'",  # prime
        "“": "'",  # left double quotation mark
        "”": "'",  # right double quotation mark
        "„": "'",  # double low-9 quotation mark
        "″": "'",  # double prime
        " ": " ",  # no-break space
        "‐": "-",  # hyphen
        "‑": "-",  # non-breaking hyphen
        "‒": "-",  # figure dash
        "–": "-",  # en dash
        "—": "-",  # em dash
        "―": "-",  # horizontal bar
        "−": "-",  # minus sign
    }
)


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def normalize_for_match(text: str) -> str:
    """Normalize text for verbatim-quote comparison, not for display.

    Decodes HTML entities, folds Unicode quote/dash/NBSP variants onto their
    ASCII equivalents, then collapses whitespace. Exact string containment
    after this normalization is still the pass/fail bar -- this only removes
    encoding noise, it never allows a fuzzy/approximate match to pass.
    """
    text = html_lib.unescape(text)
    text = text.translate(_QUOTE_NORMALIZE_MAP)
    return normalize_whitespace(text)


def load_paragraph_lookup(sections_dir: Path = DATA_SECTIONS) -> dict[str, str]:
    """Merge paragraph id -> text across every saved section file."""
    lookup: dict[str, str] = {}
    for path in sections_dir.glob("*.json"):
        section = json.loads(path.read_text())
        for para in section.get("paragraphs", []):
            lookup[para["id"]] = para["text"]
    return lookup


def check_quotes_in_paragraphs(
    source_quotes: list[str], source_paragraph_ids: list[str], paragraph_lookup: dict[str, str]
) -> tuple[bool, str]:
    """Every quote in source_quotes must individually match verbatim."""
    if not source_paragraph_ids:
        return False, "no source_paragraph_ids given"
    missing = [pid for pid in source_paragraph_ids if pid not in paragraph_lookup]
    if missing:
        return False, f"unknown paragraph id(s): {missing}"
    if not source_quotes:
        return False, "no source_quotes given"

    combined = normalize_for_match(" ".join(paragraph_lookup[pid] for pid in source_paragraph_ids))
    not_found = [q for q in source_quotes if normalize_for_match(q) not in combined]
    if not_found:
        return False, f"source_quote(s) not found verbatim in cited paragraphs: {not_found}"
    return True, ""


def _numbers_in_record(record: dict) -> dict[str, float]:
    numeric_fields = (
        "price_low",
        "price_high",
        "multiple_low",
        "multiple_high",
        "implied_price_low",
        "implied_price_high",
    )
    return {f: record[f] for f in numeric_fields if record.get(f) is not None}


def check_numbers_in_quotes(record: dict, source_quotes: list[str]) -> tuple[bool, str]:
    """Every numeric field must appear in at least one of source_quotes."""
    numbers = _numbers_in_record(record)
    if not numbers:
        return True, ""

    quote_numbers = set()
    for quote in source_quotes:
        for match in _NUMBER_RE.findall(quote):
            try:
                quote_numbers.add(float(match.replace(",", "")))
            except ValueError:
                continue

    missing = []
    for field, value in numbers.items():
        if not any(abs(value - qn) < 0.01 for qn in quote_numbers):
            missing.append(field)

    if missing:
        return False, f"field(s) not found in any source_quote: {missing}"
    return True, ""


def check_low_le_high(record: dict) -> tuple[bool, str]:
    violations = []
    for low_field, high_field in _LOW_HIGH_PAIRS:
        low, high = record.get(low_field), record.get(high_field)
        if low is not None and high is not None and low > high:
            violations.append(f"{low_field} ({low}) > {high_field} ({high})")
    if violations:
        return False, "; ".join(violations)
    return True, ""


def check_dates_valid(record: dict) -> tuple[bool, str]:
    start, end = record.get("date_start"), record.get("date_end")
    if start is None and end is None:
        return True, ""

    def _as_date(v) -> date_cls | None:
        if v is None or isinstance(v, date_cls):
            return v
        return date_cls.fromisoformat(v)

    try:
        start_d, end_d = _as_date(start), _as_date(end)
    except ValueError as exc:
        return False, f"invalid date: {exc}"

    if start_d is not None and end_d is not None and start_d > end_d:
        return False, f"date_start ({start_d}) after date_end ({end_d})"
    return True, ""


def validate_record(
    record_type: str, record: dict, paragraph_lookup: dict[str, str]
) -> dict:
    checks = {}
    checks["quotes_in_paragraphs"], reason1 = check_quotes_in_paragraphs(
        record.get("source_quotes", []), record.get("source_paragraph_ids", []), paragraph_lookup
    )
    checks["numbers_in_quotes"], reason2 = check_numbers_in_quotes(record, record.get("source_quotes", []))
    checks["low_le_high"], reason3 = check_low_le_high(record)
    checks["dates_valid"], reason4 = check_dates_valid(record)

    reasons = [r for r in (reason1, reason2, reason3, reason4) if r]
    passed = all(checks.values())

    return {
        "record_type": record_type,
        "record": record,
        "passed": passed,
        "checks": checks,
        "failure_reasons": reasons,
    }


def validate_all(
    records_by_type: dict[str, list], paragraph_lookup: dict[str, str]
) -> list[dict]:
    results = []
    for record_type, records in records_by_type.items():
        for record in records:
            data = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
            results.append(validate_record(record_type, data, paragraph_lookup))
    return results


def write_extraction_json(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2))


DATE_FORMATS = ("%B %d %Y", "%b %d %Y")


def _try_parse_date(text: str) -> date_cls | None:
    if not text:
        return None
    month_match = re.search(r"([A-Za-z]+)\s+(\d{1,2})", text)
    year_match = re.search(r"(\d{4})", text)
    if not month_match or not year_match:
        return None
    candidate = f"{month_match.group(1)} {month_match.group(2)} {year_match.group(1)}"
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    return None


def _sort_key_event(r: dict) -> tuple:
    rec = r["record"]
    d = rec.get("date_start") or _try_parse_date(rec.get("date_text", ""))
    d = date_cls.fromisoformat(d) if isinstance(d, str) else d
    return (d is None, d or date_cls.min)


def _sort_key_proposal(r: dict) -> tuple:
    rec = r["record"]
    d = _try_parse_date(rec.get("date", ""))
    return (d is None, d or date_cls.min)


def _status_marker(result: dict) -> str:
    return "" if result["passed"] else f" ⚠ VALIDATION FAILED: {'; '.join(result['failure_reasons'])}"


def _format_quotes(rec: dict) -> str:
    return "\n".join(f"  > {q}" for q in rec.get("source_quotes", []))


def _format_event(r: dict) -> str:
    rec = r["record"]
    parties = ", ".join(rec.get("parties", []))
    return (
        f"- **{rec.get('date_text')}** [{rec.get('event_type')}] ({parties}): "
        f"{rec.get('summary')}{_status_marker(r)}\n"
        f"{_format_quotes(rec)}\n"
    )


def _format_proposal(r: dict) -> str:
    rec = r["record"]
    price = ""
    if rec.get("price_low") is not None or rec.get("price_high") is not None:
        currency = rec.get("currency") or ""
        price = f", {currency}{rec.get('price_low')}-{rec.get('price_high')}"
    return (
        f"- **{rec.get('date')}** [{rec.get('proposal_kind')}] "
        f"{rec.get('proposer')} -> {rec.get('recipient')}{price} "
        f"({rec.get('consideration_type')}, status: {rec.get('status')}){_status_marker(r)}\n"
        f"{_format_quotes(rec)}\n"
    )


def _format_valuation(r: dict) -> str:
    rec = r["record"]
    multiple = ""
    if rec.get("multiple_low") is not None or rec.get("multiple_high") is not None:
        multiple = f", multiple {rec.get('multiple_low')}x-{rec.get('multiple_high')}x"
    implied = ""
    if rec.get("implied_price_low") is not None or rec.get("implied_price_high") is not None:
        implied = f", implied price {rec.get('implied_price_low')}-{rec.get('implied_price_high')}"
    assumptions = ""
    if rec.get("key_assumptions"):
        assumptions = f", assumptions: {', '.join(rec['key_assumptions'])}"
    return (
        f"- **{rec.get('advisor')}** [{rec.get('method')}] {rec.get('metric')}"
        f"{multiple}{implied}{assumptions}{_status_marker(r)}\n"
        f"{_format_quotes(rec)}\n"
    )


def write_summary_md(results: list[dict], deal_name: str, path: Path) -> None:
    events = [r for r in results if r["record_type"] == "Event"]
    proposals = [r for r in results if r["record_type"] == "Proposal"]
    valuations = [r for r in results if r["record_type"] == "ValuationAnalysis"]

    events.sort(key=_sort_key_event)
    proposals.sort(key=_sort_key_proposal)

    lines = [f"# {deal_name} -- Deal Timeline & Valuation Summary\n"]

    n_pass = sum(1 for r in results if r["passed"])
    lines.append(f"_{n_pass}/{len(results)} records passed validation._\n")

    lines.append("## Timeline\n")
    merged = events + proposals
    merged.sort(
        key=lambda r: _sort_key_event(r) if r["record_type"] == "Event" else _sort_key_proposal(r)
    )
    for r in merged:
        if r["record_type"] == "Event":
            lines.append(_format_event(r))
        else:
            lines.append(_format_proposal(r))

    lines.append("\n## Valuation Analyses\n")
    for r in valuations:
        lines.append(_format_valuation(r))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))


def run(
    records_by_type: dict[str, list], deal_name: str, deal_slug: str
) -> tuple[list[dict], Path, Path]:
    paragraph_lookup = load_paragraph_lookup()
    results = validate_all(records_by_type, paragraph_lookup)

    extraction_path = DATA_OUTPUT / f"{deal_slug}_extraction.json"
    summary_path = DATA_OUTPUT / f"{deal_slug}_summary.md"

    write_extraction_json(results, extraction_path)
    write_summary_md(results, deal_name, summary_path)

    return results, extraction_path, summary_path
