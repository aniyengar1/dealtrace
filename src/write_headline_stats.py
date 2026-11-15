"""Writes the headline stats (src.bulk_stats.compute_all) to a
versioned JSON file for the website (or any other consumer) to read,
and refreshes the same numbers into Postgres (deal_metrics,
headline_stats -- see src.deal_metrics) so the JSON file and the DB
tables can never drift apart from each other: both come from one
src.deal_metrics.refresh_all() call.

    python -m src.write_headline_stats

See docs/bulk_stats_methodology.md for the known limitations this
dataset carries (dedup gaps, acquirer-name heuristic, signing-event
recall, data-quality exclusion thresholds) -- not repeated here.
"""

import json

from src.deal_metrics import refresh_all


def main() -> None:
    summary = refresh_all()
    print(f"wrote {summary['json_path']}")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
