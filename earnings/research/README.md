# Scaling research, not live inputs

The November 20, 2026 work covers the exact 64 R1 issuers in the prior season screen. This directory is separate from production guidance/history, frozen v2 extraction, hybrid artifacts and live predictions. It imports no store or prediction module, runs no model, and never promotes observations. Agent source curation is not owner human review. The extractor experiment remains shelved; its fresh issuers are excluded by the SEC collector.

`scaling_2027q1_sources` reuses `earnings.sec.fetch` and the original SEC cache/rate limiter. It preserves all relevant source bytes/manifests under ignored `data/cache/earnings/`. It is resumable. `scaling_2027q1_packets` inventories regular results, datelines, competing companyfacts concepts and compatible Q4 parents. `scaling_2027q1_pairs` provides broad offline evidence locators only: their suggestions are not accepted extraction records, and known segment/column/tolerance errors are not corrected into a new extractor. Manual source selections, explicit exceptions and deterministic checks are applied separately in the report builder. This is not extraction evaluation or tuning of frozen v2.

The source selections are pinned by release/accession anchors in `scaling_2027q1/manual_ranges.json`; new source ordering requires another source review. No original/initial guidance status is inferred. `announcement_pairs.json` records agent-curated full official date-announcement bodies, attribution and actual observation times. Historical four-pair medians do not verify future publication dates. HTTP failures, directory/search-only results and call-only wording remain gaps. Web-rendered artifacts are labelled separately from original HTTP body hashes. Earlier unpreserved retrieval times are not invented; separate full-body rechecks record their actual observation times.

Rebuild offline from the pinned local cache:

```sh
.venv/bin/python -m earnings.research.scaling_2027q1_packets
.venv/bin/python -m earnings.research.scaling_2027q1_pairs
.venv/bin/python -m earnings.research.scaling_2027q1_report
.venv/bin/python -m earnings.research.scaling_2027q1_render
DATABASE_URL='' .venv/bin/python -m pytest tests/earnings/test_scaling_research.py -q
```

The SEC collector (`python -m earnings.research.scaling_2027q1_sources`) is the only financial network stage. The dates collector uses official IR HTTP only for date research; it has no authority to write announcement records. Cached sources are required for offline reproduction and are intentionally not committed. Financial amounts and reconciliations use Decimal; missing or conflicting source evidence blocks a row. The report is a research onboarding priority list, not permission to expand the live registry or lock predictions.
