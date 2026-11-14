"""Writes the headline stats (src.bulk_stats.compute_all) to a
versioned JSON file for the website (or any other consumer) to read.

    python -m src.write_headline_stats

See docs/bulk_stats_methodology.md for the known limitations this
dataset carries (dedup gaps, acquirer-name heuristic, signing-event
recall, data-quality exclusion thresholds) -- not repeated here.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from src.bulk_stats import compute_all

OUTPUT_PATH = Path("data/output/stats/headline_stats.json")


def _code_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def main() -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "code_commit": _code_commit(),
        "methodology_doc": "docs/bulk_stats_methodology.md",
        "stats": compute_all(),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, default=str))
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
