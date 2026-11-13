# Session 4 extraction evaluation — review required

**Quality gate FAILED. Do not promote candidates or start Session 5. Session 3’s prospective live gate remains pending.** Rule implementation and evaluation are delivered for review; this is not a claim of validated extraction quality. No LLM calls, model training, production-guidance changes, baseline/eligibility changes, website changes, merge, push or deployment.

## Frozen checkpoints

- Local annotated tag `session3-lock-ready` -> **94984fc3ce33c6e85a287738d3a617561cd0cefc**. It was created before Session 4 edits and never moved.
- **513ea03** froze gold, the development/held-out split and the isolated environment before rules were written.
- **0011c36** froze the developed rules, evaluator, canonicalizer and calendar configuration before the first held-out evaluation. Their hashes remain unchanged afterward.
- Gold SHA-256: `d6de1dd51f61e5eb4ee5f51350859dd0799494eb9cd75d8514099617c6f16b4c`. All original guidance/history file hashes remain unchanged.

Gold contains **134 unique reviewed versions, 100 release groups, 101 source documents**. Development has 96 records/72 documents; company-held-out CRWD/IOT/LULU has 38 records/29 documents. Same-release versions/exhibits stay together; the split is in `earnings/extraction/split_v1.json`. These companies were inspected in previous sessions, so this is not a pristine blind external test. No rules were tuned after observing held-out outcomes.

## Results

| Dataset | Strict TP / predicted / gold | Strict precision | Strict recall | Value/period/metric precision | Value/period/metric recall |
|---|---|---|---|---|---|
| Development | 94 / 95 / 96 | 98.95% | 97.92% | 100.00% | 98.96% |
| Held out | 23 / 48 / 38 | 47.92% | 60.53% | 64.58% | 81.58% |
| Combined (diagnostic, not independent) | 117 / 143 / 134 | 81.82% | 87.31% | 88.11% | 94.03% |

Target: >=98% precision and >=90% recall. Development meets both; held-out and combined strict results do not. Do not substitute the development or amount-only score for the failed strict held-out result.

Strict matching includes amounts, currency, basis, fiscal bounds, metric, issuance interval, filing date, status, accession and exhibit. Exact quote slices and offsets are validated independently; manually chosen long/truncated gold quote spans need not be identical. The gold is positive-only, not an exhaustive annotation of every document. Scoring therefore includes **all outputs in document+metric cells represented in gold**, including wrong fiscal periods/ranges; 44 development and 12 held-out outputs from other document+metric cells remain explicitly unjudged. No open-world precision claim is made. Metadata fields supplied from SEC inventory are not learned extraction successes.

| Field | Development correct / 96 gold | Held-out correct / 38 gold | Resolution |
|---|---|---|---|
| accession | 95 | 33 | Supplied SEC source inventory metadata |
| basis | 95 | 33 | Manual registered issuer/basis policy |
| end | 95 | 31 | Rule output (fiscal boundaries use manual calendar policy) |
| exhibit | 95 | 33 | Supplied SEC source inventory metadata |
| filed | 95 | 33 | Supplied SEC source inventory metadata |
| high | 95 | 33 | Rule output |
| issued | 94 | 33 | Rule output |
| low | 95 | 33 | Rule output |
| metric | 95 | 33 | Rule output |
| start | 95 | 31 | Rule output (fiscal boundaries use manual calendar policy) |
| status | 95 | 25 | Rule output |
| unit | 95 | 33 | Rule output |

Field-level precision/recall denominators and every expected/actual difference are in `session4_development_final.json` and `session4_heldout_v1.json`. Matching is one-to-one; partial field correctness does not make a strict record correct. There were **zero source-access gaps** in either evaluation. Unresolved issuance/reference interpretation is an extraction failure, not an inaccessible-source excuse.

## Error analysis

- **CrowdStrike:** six annual-recurring-revenue outputs were mislabeled as consolidated revenue. They then contaminated prior-candidate range comparisons and caused six otherwise value-correct revenue records to receive wrong change statuses. This violates the required ARR rejection standard. The frozen rule is not safe for production.
- **Samsara:** implied-Q4 headings were selected for two directly issued Q3 ranges; those wrong target assignments subsequently made two new Q4 initial targets look like raises. Implied calculations are not directly issued guidance.
- **lululemon:** annual prose such as “For 2026” inherited the prior quarterly context, producing nine wrong quarterly outputs. Five gold records were missed: the “will be in the range” January 2025 raise; the January 2026 “toward the high end” reaffirmation; and three bare-year annual guidance records.
- **Development residuals:** GitLab January 12 primary-document reaffirmation got January 9 as issuance; the May 11 letter reaffirmation lacked a date resolvable by the current exhibit-only date window. No missing date was replaced by the gold value.

Two strict expected-failure unit tests preserve the known ARR and implied-quarter weaknesses. They are not passing validation checks. No post-holdout rule fix or retuning is hidden in these reported scores. All candidates have `review_required=true`, and production code does not consume these outputs.

### Every miss or field mismatch

| Split / issuer | Gold record | SEC source | Error |
|---|---|---|---|
| Development / GTLB | `1871a1e8-7e00-5f1c-8e28-a262fa6ce510` | [0001653482-26-000009 8-K Item 7.01 (primary document; no exhibit)](https://www.sec.gov/Archives/edgar/data/1653482/000165348226000009/gtlb-20260109.htm) | {"issued": {"actual": {"end": "2026-01-09", "precision": "day", "start": "2026-01-09"}, "expected": {"end": "2026-01-12", "precision": "day", "start": "2026-01-12"}}} |
| Development / GTLB | `8b7bce64-dc28-5fcf-87c4-1a4028543b8a` | [0001653482-26-000095 99.1](https://www.sec.gov/Archives/edgar/data/1653482/000165348226000095/exhibit991-letterfromwilla.htm) | MISS: reaffirmed quarterly_consolidated_revenue 2026-02-01–2026-04-30; 253000000.0–255000000.0 |
| Held out / CRWD | `6a52f11e-61b8-554e-826f-4dc433be1b18` | [0001535527-26-000007 99.1](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000007/crwd-20260303xex991.htm) | {"status": {"actual": "lowered", "expected": "initial"}} |
| Held out / CRWD | `7bc596a9-4d6e-5f18-8f95-76b424343da6` | [0001535527-26-000007 99.1](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000007/crwd-20260303xex991.htm) | {"status": {"actual": "lowered", "expected": "initial"}} |
| Held out / CRWD | `49a3f9b5-1f5a-54cd-ab80-c173b4ed70fd` | [0001535527-26-000022 99.1](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000022/crwd-20260603xex991.htm) | {"status": {"actual": "lowered", "expected": "initial"}} |
| Held out / CRWD | `a31172b0-3168-5009-8472-59282faee637` | [0001535527-26-000022 99.1](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000022/crwd-20260603xex991.htm) | {"status": {"actual": "lowered", "expected": "raised"}} |
| Held out / CRWD | `20136ed5-16e2-50dc-b46c-8f4833b1db90` | [0001535527-26-000029 99.1](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000029/crwd-20260826xex991.htm) | {"status": {"actual": "lowered", "expected": "raised"}} |
| Held out / CRWD | `f6ff18dc-8880-5f65-b254-cdbbf1a488ba` | [0001535527-26-000029 99.1](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000029/crwd-20260826xex991.htm) | {"status": {"actual": "lowered", "expected": "initial"}} |
| Held out / IOT | `8314785d-3123-5174-be7d-d1f8d31b4d29` | [0001642896-24-000059 99.1](https://www.sec.gov/Archives/edgar/data/1642896/000164289624000059/samsaraepr-q22025.htm) | {"end": {"actual": "2025-02-01", "expected": "2024-11-02"}, "start": {"actual": "2024-11-03", "expected": "2024-08-04"}} |
| Held out / IOT | `fddad161-7f56-5eee-81a0-545454b32964` | [0001642896-24-000073 99.1](https://www.sec.gov/Archives/edgar/data/1642896/000164289624000073/samsaraepr-q32025.htm) | {"status": {"actual": "raised", "expected": "initial"}} |
| Held out / IOT | `be526f84-8160-5a5f-a624-15c39feec219` | [0001642896-25-000070 99.1](https://www.sec.gov/Archives/edgar/data/1642896/000164289625000070/samsaraepr-q22026.htm) | {"end": {"actual": "2026-01-31", "expected": "2025-11-01"}, "start": {"actual": "2025-11-02", "expected": "2025-08-03"}} |
| Held out / IOT | `56685baa-a236-506c-abc3-dda2a073ce7a` | [0001628280-25-055355 99.1](https://www.sec.gov/Archives/edgar/data/1642896/000162828025055355/samsaraepr-q32026.htm) | {"status": {"actual": "raised", "expected": "initial"}} |
| Held out / LULU | `428042f8-d727-51ae-9c58-b562f949a824` | [0001397187-25-000004 99.1](https://www.sec.gov/Archives/edgar/data/1397187/000139718725000004/lulu-20250113xex991.htm) | MISS: raised quarterly_consolidated_revenue 2024-10-28–2025-02-02; 3560000000.000–3580000000.000 |
| Held out / LULU | `a7933c24-91b4-555b-bacc-6c30c5947967` | [0001397187-26-000005 99.1](https://www.sec.gov/Archives/edgar/data/1397187/000139718726000005/lulu-20260112xex991.htm) | MISS: reaffirmed quarterly_consolidated_revenue 2025-11-03–2026-02-01; 3500000000.000–3585000000.000 |
| Held out / LULU | `97e0b842-2159-5e01-9e6f-c0e00779a660` | [0001397187-26-000019 99.1](https://www.sec.gov/Archives/edgar/data/1397187/000139718726000019/lulu-20260201xex991.htm) | MISS: initial consolidated_revenue 2026-02-02–2027-01-31; 11350000000.000–11500000000.000 |
| Held out / LULU | `5e5e884b-d835-52b8-96b1-b89aee84dd31` | [0001397187-26-000077 99.1](https://www.sec.gov/Archives/edgar/data/1397187/000139718726000077/lulu-20260503xex991.htm) | MISS: lowered consolidated_revenue 2026-02-02–2027-01-31; 11000000000.000–11150000000.000 |
| Held out / LULU | `922c08aa-ed21-56eb-8898-fe746b19f388` | [0001397187-26-000126 99.1](https://www.sec.gov/Archives/edgar/data/1397187/000139718726000126/lulu-20260802xex991.htm) | MISS: lowered consolidated_revenue 2026-02-02–2027-01-31; 10350000000.000–10500000000.000 |

### Unmatched in-scope candidates

All unmatched candidates below count as strict false positives; they are not discarded after inspecting gold. Full canonical quotes and offsets are in the adjacent candidate JSON.

| Split / issuer | Candidate ID | Source | Claimed target and amount |
|---|---|---|---|
| Held out / LULU | `889a4330-9a8d-53ba-a0af-5f5e4f82a5e8` | [0001397187-24-000033](https://www.sec.gov/Archives/edgar/data/1397187/000139718724000033/lulu-20240728xex991.htm) | quarterly_consolidated_revenue, 2024-07-29–2024-10-27, USD 10375000000.000–10475000000.000 |
| Held out / LULU | `1438327b-31ae-51ba-a302-c306dc6ae067` | [0001397187-24-000040](https://www.sec.gov/Archives/edgar/data/1397187/000139718724000040/lulu-20241027xex991.htm) | quarterly_consolidated_revenue, 2024-10-28–2025-02-02, USD 10452000000.000–10487000000.000 |
| Held out / LULU | `1d051702-df57-5c06-9b3a-d6f7c82309d9` | [0001397187-25-000012](https://www.sec.gov/Archives/edgar/data/1397187/000139718725000012/lulu-20250202xex991.htm) | quarterly_consolidated_revenue, 2025-02-03–2025-05-04, USD 11150000000.000–11300000000.000 |
| Held out / LULU | `94ce37ea-9dff-5a47-97dd-5600bd40a101` | [0001397187-25-000026](https://www.sec.gov/Archives/edgar/data/1397187/000139718725000026/lulu-20250504xex991.htm) | quarterly_consolidated_revenue, 2025-05-05–2025-08-03, USD 11150000000.000–11300000000.000 |
| Held out / LULU | `113d9346-a10e-562d-a423-c4148e54f63b` | [0001397187-25-000038](https://www.sec.gov/Archives/edgar/data/1397187/000139718725000038/lulu-20250803xex991.htm) | quarterly_consolidated_revenue, 2025-08-04–2025-11-02, USD 10850000000.000–11000000000.000 |
| Held out / LULU | `4262dfd5-098a-5e7e-9f0e-f9ac4b0879fb` | [0001397187-25-000054](https://www.sec.gov/Archives/edgar/data/1397187/000139718725000054/lulu-20251102xex991.htm) | quarterly_consolidated_revenue, 2025-11-03–2026-02-01, USD 10962000000.000–11047000000.000 |
| Held out / CRWD | `5eb8492d-e048-5e50-abd8-e4cf695e99cb` | [0001535527-26-000007](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000007/crwd-20260303xex991.htm) | quarterly_consolidated_revenue, 2026-02-01–2026-04-30, USD 5501800000.0–5503800000.0 |
| Held out / CRWD | `59679caf-88d6-5144-bc8d-d6f97a438a14` | [0001535527-26-000007](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000007/crwd-20260303xex991.htm) | consolidated_revenue, 2026-02-01–2027-01-31, USD 6465800000.0–6516400000.0 |
| Held out / LULU | `ced4868b-dfba-5ff5-8e50-160656157d22` | [0001397187-26-000019](https://www.sec.gov/Archives/edgar/data/1397187/000139718726000019/lulu-20260201xex991.htm) | quarterly_consolidated_revenue, 2026-02-02–2026-05-03, USD 11350000000.000–11500000000.000 |
| Held out / CRWD | `4cfa3df4-de37-5513-8703-2402a699279d` | [0001535527-26-000022](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000022/crwd-20260603xex991.htm) | quarterly_consolidated_revenue, 2026-05-01–2026-07-31, USD 5792600000.0–5794600000.0 |
| Held out / CRWD | `ea7c6ace-fcd1-5e90-b345-becee8618b82` | [0001535527-26-000022](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000022/crwd-20260603xex991.htm) | consolidated_revenue, 2026-02-01–2027-01-31, USD 6531700000.0–6555500000.0 |
| Held out / LULU | `15a26e63-8440-5d2a-8aa7-7a5666932033` | [0001397187-26-000077](https://www.sec.gov/Archives/edgar/data/1397187/000139718726000077/lulu-20260503xex991.htm) | quarterly_consolidated_revenue, 2026-05-04–2026-08-02, USD 11000000000.000–11150000000.000 |
| Held out / CRWD | `295280f8-7d9d-5e32-8f7c-b27b61c028b4` | [0001535527-26-000029](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000029/crwd-20260826xex991.htm) | quarterly_consolidated_revenue, 2026-08-01–2026-10-31, USD 6184400000.0–6188400000.0 |
| Held out / CRWD | `04e22185-bc17-53cd-808c-ae9afc3d4b12` | [0001535527-26-000029](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000029/crwd-20260826xex991.htm) | consolidated_revenue, 2026-02-01–2027-01-31, USD 6603000000.0–6611900000.0 |
| Held out / LULU | `be013eb8-5e89-5de3-8b06-2dec9b4415c4` | [0001397187-26-000126](https://www.sec.gov/Archives/edgar/data/1397187/000139718726000126/lulu-20260802xex991.htm) | quarterly_consolidated_revenue, 2026-08-03–2026-11-01, USD 10350000000.000–10500000000.000 |

## Provenance, reproducibility and isolation

New code lives only in `earnings/extraction/` and the external `earnings/lock_ready/check.py` harness. `extract(text, metadata)` never reads gold values, production guidance or the DB. Source metadata is supplied; manual fiscal-calendar and unqualified consolidated-revenue basis assumptions are explicitly documented. Money parsing uses Decimal. Explicit reaffirmations retain prior extracted-candidate edges rather than inventing a new numeric quote.

Quotes have exact half-open Unicode offsets into saved whitespace-normalized visible SEC exhibit text, with raw-body and canonical-text hashes; they are not claimed to be HTML byte offsets. Source versions are cached under the existing SEC convention. `earnings.extraction.replay` verifies the pinned source text and frozen implementation and reproduced the held-out strict metrics, fields, matches and errors exactly.

Python **3.14.7** and the entire installed dependency set are pinned in `earnings/lock_ready/environment.json` and `requirements.lock`. The existing isolated `.venv` was preserved; no package installation or shared-environment change occurred. The tag freezes code, not evidence: real locking must still refresh source evidence and use actual time.

## Lock workflow preservation and regression

All **64 protected code/data/schema files** match the reviewed tag, including every existing earnings root Python module, fetcher, requirements, company/guidance/history/announcement files and migrations. No module imported by the lock workflow was modified. Installed dependency versions also match the captured freeze.

An isolated `git archive` copy of the tag was exercised without switching either worktree. Required earnings migrations were checked against the actual DB, and production read queries succeeded. Tag and HEAD outputs on identical synthetic fixed inputs/time are **identical**, including eligibility, target periods, selected guidance IDs, historical input IDs, probabilities, method and rejection reasons. Seven scenarios cover outside/inside windows, exact deadline, withdrawn guidance, stale actuals, already-public results and missing history. Synthetic proposals are not live predictions.

Actual-clock runs used PostgreSQL **BEGIN READ ONLY**, additionally suppressing history ingestion and ledger insertion. No prediction ID or made_at was fabricated. All connections rolled back. Both reviewed and current versions reported four companies outside the window and six with unverified dates. Only execution clock times differ in these real runs; rejection classifications agree.

Final actual-clock dry run: **2026-11-13T02:39:13.685520+00:00** through **2026-11-13T02:39:13.708773+00:00**; transaction_read_only=on; real ledger count **0 -> 0**; locked predictions **0**; no missing unimported historical IDs. This dry run does **not** pass the prospective live gate.

Evidence: `session4_lock_regression_summary.json`, the tag/HEAD fixed-input outputs, and all actual-clock dry-run outputs under `earnings/validation/`. No future waiting process or automatic scheduling was created.

## Next manual live dates

All four currently verified releases have after-close wording, not an exact results-publication timestamp. America/New_York is EST on these dates; use midnight at the start of the release date, strictly before the deadline.

| Company | Earliest eligibility | Strict deadline |
|---|---|---|
| OKTA | November 17, 2026 00:00 EST / 05:00 UTC | December 1, 2026 00:00 EST / 05:00 UTC |
| CRM | November 18, 2026 00:00 EST / 05:00 UTC | December 2, 2026 00:00 EST / 05:00 UTC |
| IOT | November 19, 2026 00:00 EST / 05:00 UTC | December 3, 2026 00:00 EST / 05:00 UTC |
| S | November 19, 2026 00:00 EST / 05:00 UTC | December 3, 2026 00:00 EST / 05:00 UTC |

CRWD/MDB full original-source access remains unresolved; ADBE has only a call listing; PD/GTLB/LULU remain unverified. These are evidence gaps, not claims of no announcement. Existing source records and prior reports were preserved. Before a real eligible lock, follow the strict fresh-source review and already-public checks in the Session 3 review; never use Session 4 candidates automatically. Exact manual commands are in `earnings/lock_ready/README.md`.

## Tests, commands and stop

Complete pytest: **384 passed, 3 skipped, 2 expected failures**. The expected failures are the documented quality gaps, not production lock regressions. The first full run exposed an existing synthetic scoring fixture using UTC date instead of the New York filing day after midnight. Only that test fixture was corrected, with a rollover test; production `score_live.py` and all lock imports remain unchanged.

```sh
.venv/bin/python -m earnings.extraction.evaluate --split development --output /tmp/crosscheck-dev-new.json
.venv/bin/python -m earnings.extraction.replay earnings/validation/session4_heldout_v1.json --output /tmp/crosscheck-heldout-replay-new.json
.venv/bin/python earnings/lock_ready/check.py --code-root . --output /tmp/crosscheck-lock-dry-run-new.json
.venv/bin/python -m pytest -q
```

**Stop for review before Session 5.** The extractor needs further work and fresh evaluation data before its failed held-out quality gate can be reassessed. No authorization to add LLM calls was assumed.
