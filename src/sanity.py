"""Deal-level sanity checks: do this extraction's records look internally
consistent, without needing a hand-built gold answer key? These check
structural invariants any correct extraction of any deal should satisfy,
so they run automatically after every live run (see run.py), not just
the deals with a benchmark:

- the final (accepted, or most recent if none is tagged "accepted")
  Proposal's price matches the per-share cash consideration stated on
  the proxy's own cover page
- a signing Event exists and names both the target and the acquirer
- every event date falls within [earliest event, signing + 1 year]
- at least one Proposal was extracted

None of these need to know what actually happened in the deal -- they're
checking the extraction against the proxy's own cover page and against
itself, which is why they don't need a gold file.
"""

import re
from datetime import date as date_cls
from datetime import timedelta
from typing import Optional

from src.validate import _try_parse_date

NUMBER_TOLERANCE = 0.01

# Every DEFM14A checked so far (10 deals, 2 different filing-agent
# templates) states the per-share cash consideration exactly this way,
# once, near the very top of the cover letter: "...you will be entitled
# to receive $157.00 in cash...for each share...". Takes the first match
# since that's always the real consideration, not a later incidental
# mention (e.g. dissenters'-rights "fair value" language reusing the same
# number further down).
_CONSIDERATION_RE = re.compile(r"entitled to receive\s+\$([\d,]+\.\d{2})\s+in cash", re.IGNORECASE)


def extract_proxy_consideration(html: str) -> Optional[float]:
    """The per-share cash merger consideration stated on the proxy's own
    cover letter. None if the filing doesn't use this exact phrasing.
    """
    match = _CONSIDERATION_RE.search(html)
    if match is None:
        return None
    return float(match.group(1).replace(",", ""))


def _as_dict(record) -> dict:
    return record.model_dump(mode="json") if hasattr(record, "model_dump") else record


def _as_date_value(value) -> Optional[date_cls]:
    if value is None or isinstance(value, date_cls):
        return value
    return date_cls.fromisoformat(value)


def check_final_price_matches_consideration(
    records_by_type: dict[str, list], proxy_consideration: Optional[float]
) -> tuple[bool, str]:
    proposals = [_as_dict(p) for p in records_by_type.get("Proposal", [])]
    if not proposals:
        return False, "no proposals extracted to compare against"
    if proxy_consideration is None:
        return False, "could not find a per-share consideration on the proxy's cover page"

    accepted = [p for p in proposals if p.get("status") == "accepted"]
    candidates = accepted if accepted else proposals

    def sort_key(p: dict) -> tuple:
        d = _try_parse_date(p.get("date", "") or "")
        return (d is None, d or date_cls.min)

    final = max(candidates, key=sort_key)
    final_price = final.get("price_high")
    if final_price is None:
        final_price = final.get("price_low")
    if final_price is None:
        return False, "final proposal has no price to compare"

    if abs(final_price - proxy_consideration) < NUMBER_TOLERANCE:
        return True, f"final proposal ${final_price:.2f} matches proxy consideration ${proxy_consideration:.2f}"
    return (
        False,
        f"final proposal ${final_price:.2f} != proxy consideration ${proxy_consideration:.2f}",
    )


def check_signing_event_exists(
    records_by_type: dict[str, list], target_name: str, acquirer_name: str
) -> tuple[bool, str]:
    events = [_as_dict(e) for e in records_by_type.get("Event", [])]
    signings = [e for e in events if e.get("event_type") == "signing"]
    if not signings:
        return False, "no signing event found"

    for e in signings:
        parties_text = " ".join(e.get("parties") or []).lower()
        if target_name.lower() in parties_text and acquirer_name.lower() in parties_text:
            return True, f"signing event found with {target_name!r} and {acquirer_name!r} in parties"
    return (
        False,
        f"signing event(s) found, but none list both {target_name!r} and {acquirer_name!r} in parties",
    )


def check_event_dates_within_window(records_by_type: dict[str, list]) -> tuple[bool, str]:
    events = [_as_dict(e) for e in records_by_type.get("Event", [])]
    dates = []
    for e in events:
        for field in ("date_start", "date_end"):
            d = _as_date_value(e.get(field))
            if d is not None:
                dates.append(d)
    if not dates:
        return False, "no dated events to check"

    signing_dates = [
        _as_date_value(e.get("date_start")) for e in events if e.get("event_type") == "signing"
    ]
    signing_dates = [d for d in signing_dates if d is not None]
    if not signing_dates:
        return False, "no signing event with a resolved date to anchor the window"

    window_start = min(dates)
    window_end = max(signing_dates) + timedelta(days=365)

    out_of_range = sorted({d for d in dates if d < window_start or d > window_end})
    if out_of_range:
        shown = ", ".join(d.isoformat() for d in out_of_range)
        return (
            False,
            f"{len(out_of_range)} event date(s) outside [{window_start}, {window_end}]: {shown}",
        )
    return True, f"all event dates within [{window_start}, {window_end}] (signing + 1 year)"


def check_has_at_least_one_proposal(records_by_type: dict[str, list]) -> tuple[bool, str]:
    n = len(records_by_type.get("Proposal", []))
    if n >= 1:
        return True, f"{n} proposal(s) found"
    return False, "no proposals extracted"


def run(
    records_by_type: dict[str, list], html: str, target_name: str, acquirer_name: str
) -> list[dict]:
    """Run all deal-level sanity checks; return [{name, passed, detail}]."""
    proxy_consideration = extract_proxy_consideration(html)
    checks = [
        (
            "final_price_matches_consideration",
            check_final_price_matches_consideration(records_by_type, proxy_consideration),
        ),
        (
            "signing_event_exists",
            check_signing_event_exists(records_by_type, target_name, acquirer_name),
        ),
        ("event_dates_within_window", check_event_dates_within_window(records_by_type)),
        ("has_at_least_one_proposal", check_has_at_least_one_proposal(records_by_type)),
    ]
    return [{"name": name, "passed": passed, "detail": detail} for name, (passed, detail) in checks]


def format_report(deal_name: str, results: list[dict]) -> str:
    lines = [f"=== Sanity checks: {deal_name} ==="]
    for r in results:
        tag = "PASS" if r["passed"] else "FLAG"
        lines.append(f"[{tag}] {r['name']}: {r['detail']}")
    return "\n".join(lines)
