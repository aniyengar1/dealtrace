# Session 4 rule extraction research

**Quality gate FAILED on held-out companies. Do not promote these candidates.** No LLM calls, model training, website changes or production-guidance replacement. All outputs are research candidates with `review_required=true`; neither the guidance loader nor the live baseline reads this directory's candidates.

## Fixed gold and split

`gold_v1.json` is an immutable snapshot of all 134 unique reviewed guidance versions from `earnings/guidance/` and `earnings/history/`, preserving original record IDs and source-file hashes. SHA-256: `d6de1dd51f61e5eb4ee5f51350859dd0799494eb9cd75d8514099617c6f16b4c`. Snapshot and split were committed as **513ea03 before rules were written**. Do not change this dataset to make the score improve.

Development: 96 versions across Adobe, Salesforce, GitLab, MongoDB, Okta, PagerDuty and SentinelOne. Held out by company: 38 versions across CrowdStrike, Samsara and lululemon. All versions/exhibits for an issuer/accession stay together, including amendments. The 100 release groups are recorded in the snapshot. Because the author inspected these companies in earlier sessions, this is a development holdout, not a pristine blind external test.

Rules and final development evaluation were frozen in **0011c36 before the first held-out evaluation**. `rules_frozen_v1.json` pins rules, evaluator, canonicalizer and calendar configuration hashes. Held-out errors were inspected only after that evaluation. No extraction-rule tuning followed. Further work needs a new method version and fresh independent evaluation data; this holdout has now been consumed.

## Method and provenance

Fetch only SEC URLs using the existing `earnings.sec.fetch` / `src.fetch` rate limiter, retry and retained cache. Use SEC corpus metadata for company, accession, exhibit and filing date. These are supplied provenance fields, not inferred from prose. No gold amount, target period, status, quote or date is passed to `extract()`.

Regex rules identify revenue-labelled target sentences and adjacent guidance-table columns, amounts/units, fiscal labels, date strings and explicit reaffirmation references. All amount math uses Decimal. Reaffirmation amounts can come only from an earlier extracted candidate, with a retained `carried_from_candidate_id`; they do not come from gold or production records. Batch status inference compares earlier candidates, and is consequently vulnerable to a prior extraction error, as the held-out results demonstrate. No missing amount is replaced by zero.

Exact fiscal boundaries come from separately documented manual issuer-calendar policies in `calendars.json`, not from the gold target dates. The existing registered calendars and SEC boundary evidence are in `earnings/companies.json` (ADBE, IOT and LULU quarter `boundary_evidence`), with previously audited 52/53-week conventions. Monthly fiscal years end January 31. Weekly calendars use nearest-weekday year ends and retain a 14-week Q4 where applicable. Unqualified issuer revenue is interpreted as consolidated reported USD under a manual scope convention. These are **manual metadata assumptions**, not claims that every boundary/basis was extracted from the exhibit.

The canonical document is BeautifulSoup visible text with scripts/styles/ix:header removed and whitespace collapsed. Quotes are exact slices of that saved text. `quote_start`/`quote_end` are half-open **Unicode character offsets in canonical text**, not HTML byte offsets. Each candidate carries the SEC raw-body hash, canonical-text hash, accession, exhibit and URL. Cached raw bodies and canonical texts are retained under `data/cache/earnings/`; source hashes and canonical cache paths are recorded in each evaluation report. Unsupported PDFs and unresolved fields are source/review gaps, not invented values.

Generic validations reject several segment/subscription/organic/constant-currency/growth-only cases, reversed ranges and missing units/fiscal labels. They are **not sufficient**: frozen v1 still misidentifies spelled-out annual recurring revenue, implied-quarter columns and some annual prose. These unsafe outputs remain visible in the error report and quarantined as research candidates. Two strict expected-failure tests document the ARR and implied-quarter gaps. No production adoption is authorized by passing the other unit tests.

## Scoring definitions and limitations

Strict exact-record fields: low, high, unit, basis, fiscal start/end, metric, issuance interval, filing date, status, accession and exhibit. A field mismatch is one false-positive candidate and one false-negative gold record; fully missing and unmatched records are also reported. Quotes must independently match their exact offsets; they need not match the manual annotator's arbitrary longer/truncated quote span.

The fixed gold is positive-only and does not exhaustively annotate every annual and quarterly target in every release. Therefore the predeclared scoring scope is **document + metric cells represented by gold**. Within those cells, all candidates count, including wrong fiscal periods and extra ranges. Other cells are explicitly unjudged, not counted as correct: development 44, held-out 12. These precision figures are benchmark-scoped; they do not establish open-world precision over all output candidates. Metadata-field accuracy is reported separately and must not be mistaken for learned extraction quality.

| Split | Strict TP / predictions / gold | Strict precision | Strict recall | Value/period/metric precision / recall |
|---|---|---|---|---|
| Development | 94 / 95 / 96 | 98.95% | 97.92% | 100.00% / 98.96% |
| Held out | 23 / 48 / 38 | 47.92% | 60.53% | 64.58% / 81.58% |
| Combined, diagnostic only | 117 / 143 / 134 | 81.82% | 87.31% | 88.11% / 94.03% |

The development split meets 98% precision / 90% recall. Held-out and combined strict scores do not. Do not declare the extractor validated or proceed to Session 5 on the strength of development performance.

## Commands

New output paths are required; previous runs are never overwritten.

```sh
.venv/bin/python -m earnings.extraction.evaluate --split development --output /tmp/crosscheck-dev-new.json
.venv/bin/python -m earnings.extraction.evaluate --split heldout --output /tmp/crosscheck-heldout-new.json
.venv/bin/python -m earnings.extraction.replay earnings/validation/session4_heldout_v1.json --output /tmp/crosscheck-heldout-pinned-replay.json
.venv/bin/python -m pytest tests/earnings/test_extraction.py -q
```

Each evaluation writes an adjacent `.candidates.json` file. The first two commands use cached/fetched SEC documents; the replay command uses the pinned canonical source versions and rejects integrity drift or unavailable original versions. It verifies the same strict/field scores, matches and errors. A replay is not a new independent evaluation. Earlier development tuning diagnostics remain in the local cache; the final development and first held-out reports are committed. Full per-record misses, expected/actual field differences, source gaps, input manifests and candidate IDs are in the reports under `earnings/validation/`.
