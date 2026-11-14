"""Full-dataset quality report: runs the pure, no-LLM validate/sanity layer
(src.bulk_quality_check.check_one) against every status=="done" bulk result,
not just the 10-deal pilot.

    python -m src.bulk_quality_report

Writes the full per-deal report to data/output/bulk_quality_report.json
(reused by src.load_bulk's pass/quarantine decision) and prints an
aggregate summary: overall quote-match rate, sanity-check pass rates, and
deals failing badly, grouped by failure type.

A deal "fails badly" if its quote_match_rate < QUOTE_MATCH_FAIL_THRESHOLD
or it has no extracted Event with event_type=="signing" at all. These are
also the two conditions src.load_bulk uses to decide pass-vs-quarantine
for loading.

Note: sanity.run()'s own "signing_event_exists" check additionally
requires the DB's raw EDGAR company name and a guessed short acquirer
name to both literally appear in the signing event's parties text --
that's a much stricter, name-formatting-sensitive bar (fails on things
like "WATERS CORP /DE/" vs "Waters"), so it is NOT used here as the
"no signing event" criterion; has_signing_event below checks only for
event_type=="signing" presence, which is what the quarantine decision
and this report's failure classification actually care about. The
stricter sanity result is still included in the per-deal report and in
sanity_check_pass_rates for visibility.
"""

import glob
import json
from collections import Counter
from pathlib import Path

from src.bulk_quality_check import check_one
from src.bulk_run import BULK_OUTPUT_DIR

QUOTE_MATCH_FAIL_THRESHOLD = 0.80
REPORT_PATH = Path("data/output/bulk_quality_report.json")


def failure_type(report: dict) -> str:
    """Classifies a failing-badly report into one bucket. Checked in this
    order so a deal with both problems is counted once, under the more
    fundamental failure (no signing event found at all implies the deal's
    timeline is unusable regardless of quote-match rate)."""
    qmr = report.get("quote_match_rate")
    if not report["has_signing_event"]:
        return "no_signing_event_at_all"
    if qmr is None:
        return "no_validatable_records"
    if qmr < QUOTE_MATCH_FAIL_THRESHOLD:
        return "low_quote_match"
    return "other"


def build_report() -> list[dict]:
    reports = []
    for path in sorted(glob.glob(str(BULK_OUTPUT_DIR / "*.json"))):
        result = json.loads(Path(path).read_text())
        if result.get("status") != "done":
            continue
        report = check_one(result)
        report["has_signing_event"] = any(
            e.get("event_type") == "signing" for e in result["events"]
        )
        report["result_path"] = path
        report["row"] = result["row"]
        reports.append(report)
    return reports


def summarize(reports: list[dict]) -> dict:
    n = len(reports)
    with_records = [r for r in reports if r.get("quote_match_rate") is not None]
    quote_match_rates = [r["quote_match_rate"] for r in with_records]
    validation_pass_rates = [r["validation_pass_rate"] for r in with_records]

    sanity_names = sorted({name for r in reports for name in r["sanity"]})
    sanity_pass_rates = {
        name: sum(1 for r in reports if r["sanity"].get(name, {}).get("passed")) / n
        for name in sanity_names
    }

    failing_badly = []
    for r in reports:
        qmr = r.get("quote_match_rate")
        bad = (not r["has_signing_event"]) or qmr is None or qmr < QUOTE_MATCH_FAIL_THRESHOLD
        if bad:
            failing_badly.append(r)

    by_type = Counter(failure_type(r) for r in failing_badly)

    return {
        "n_deals": n,
        "overall_quote_match_rate_mean": sum(quote_match_rates) / len(quote_match_rates) if quote_match_rates else None,
        "overall_validation_pass_rate_mean": sum(validation_pass_rates) / len(validation_pass_rates) if validation_pass_rates else None,
        "n_deals_with_no_validatable_records": n - len(with_records),
        "sanity_check_pass_rates": sanity_pass_rates,
        "n_failing_badly": len(failing_badly),
        "failing_badly_by_type": dict(by_type),
        "failing_badly_deals": [
            {
                "target_name": r["target_name"],
                "form_type": r["form_type"],
                "quote_match_rate": r.get("quote_match_rate"),
                "signing_event_detail": r["sanity"].get("signing_event_exists", {}).get("detail"),
                "failure_type": failure_type(r),
            }
            for r in failing_badly
        ],
    }


def main() -> None:
    reports = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(reports, indent=2, default=str))
    summary = summarize(reports)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
