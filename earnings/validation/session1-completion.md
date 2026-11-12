# Bounded Session 1 completion evidence

As of November 11, 2026. Branch earnings. Previous commits and interface preserved. No merge, push or deployment. This is Session 1 evidence, not the Session 2 full-universe audit.

## Gate status

Implementation and Adobe/CrowdStrike reconciliation pass. Full Python suite: 312 passed, 3 pre-existing uncached-filing skips; 89 earnings tests passed. Existing frontend suite: 18 passed. Dependency check and diff whitespace check pass. Remaining external evidence gaps are recorded below.

## Implemented

Eleven current-quarter guidance versions across all ten companies, with MongoDB September 28 reaffirmation. Annual and quarterly selection/calculations are distinct. Quarterly implied growth compares the entire range with the prior quarter; no annual YTD subtraction. Selected-version quarterly outcomes check inclusive boundaries, issuance/filing availability, exact period/basis, and a separate result-specific comparability review. No probabilities or live ledger were added.

## Adobe and CrowdStrike annual reconciliation

All table amounts are USD millions. Exact Decimal ratios, all input IDs, source hashes and full records appear in session1-completion.json.

### ADBE

Annual guidance: 26576.000–26626.000; issue/file date 2026-09-10/2026-09-10; [0000796343-26-000147, Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/796343/000079634326000147/adbeex991q326.htm). Fiscal period 2025-11-29–2026-11-27. Guidance version `04d7cd94-ee0a-56f9-b9d5-7329de346f83`.

| Input | Fiscal period | USD million | Accession | Filed / available | Record ID |
|---|---|---:|---|---|---|
| actual_ytd | 2025-11-29–2026-08-28 | 19776 | 0000796343-26-000156 | 2026-09-22 | `a083ce84-caea-59aa-8a68-ec2ad3c2b407` |
| prior_annual | 2024-11-30–2025-11-28 | 23769 | 0000796343-26-000003 | 2026-01-15 | `a2ef2fac-145a-5869-acfa-6a56ab7dd9c4` |
| prior_remaining | 2025-08-30–2025-11-28 | 6194 | 0000796343-26-000003 | 2026-09-22 | `7abe3801-66c8-52b4-b8cc-f97764e73c36` |
| prior_ytd | 2024-11-30–2025-08-29 | 17575 | 0000796343-26-000156 | 2026-09-22 | `cae93e71-4df5-5aeb-bafc-cb3108465d29` |

Calculation `9f40e737-5a4d-548f-a763-a0bf3ae8c9fd`: remaining revenue 6800.000–6850.000; required growth 9.783662%–10.590894%. Formula revenue-hurdle-v1-decimal50; policy manual-freshness-v1 (135-day actuals / 150-day guidance, manual assumptions).

The derived remainder retains both annual and YTD parent IDs; its availability is the later parent filing date. Its accession is the annual parent, not a claim of a separately filed derived fact.

Company statement (USD millions): `Total revenue 6,760 5,988 19,776 17,575`. Columns: current quarter, prior quarter, current YTD/annual, prior YTD/annual. [SEC earnings release](https://www.sec.gov/Archives/edgar/data/796343/000079634326000147/adbeex991q326.htm). Exact statement-row and selected companyfacts reconciliation; discrepancy 0%.

Company statement (USD millions): `Total revenue 6,194 5,606 23,769 21,505`. Columns: current quarter, prior quarter, current YTD/annual, prior YTD/annual. [SEC earnings release](https://www.sec.gov/Archives/edgar/data/796343/000079634325000135/adbeex991q425.htm). Exact statement-row and selected companyfacts reconciliation; discrepancy 0%.

### CRWD

Annual guidance: 5991.1000–6011.1000; issue/file date 2026-08-26/2026-08-26; [0001535527-26-000029, Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000029/crwd-20260826xex991.htm). Fiscal period 2026-02-01–2027-01-31. Guidance version `20136ed5-16e2-50dc-b46c-8f4833b1db90`.

| Input | Fiscal period | USD million | Accession | Filed / available | Record ID |
|---|---|---:|---|---|---|
| actual_ytd | 2026-02-01–2026-07-31 | 2856.526 | 0001535527-26-000031 | 2026-08-27 | `76c32b45-9444-5cb0-b1d8-3c83c8ca26a6` |
| prior_annual | 2025-02-01–2026-01-31 | 4812.005 | 0001535527-26-000010 | 2026-03-05 | `f9e2446a-2913-5e54-821f-6b3cddc548e3` |
| prior_remaining | 2025-08-01–2026-01-31 | 2539.619 | 0001535527-26-000010 | 2026-08-27 | `1dac35de-8ae7-5239-8f39-ce8e4aa7f4d7` |
| prior_ytd | 2025-02-01–2025-07-31 | 2272.386 | 0001535527-26-000031 | 2026-08-27 | `8a5f1cea-4951-57fb-b7be-0958074783da` |

Calculation `ad7fe379-8d9a-590c-89bf-f08d94c1f927`: remaining revenue 3134.5740–3154.5740; required growth 23.426939%–24.214459%. Formula revenue-hurdle-v1-decimal50; policy manual-freshness-v1 (135-day actuals / 150-day guidance, manual assumptions).

The derived remainder retains both annual and YTD parent IDs; its availability is the later parent filing date. Its accession is the annual parent, not a claim of a separately filed derived fact.

Company statement (USD thousands): `Total revenue 1,470,897 1,168,952 2,856,526 2,272,386`. Columns: current quarter, prior quarter, current YTD/annual, prior YTD/annual. [SEC earnings release](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000029/crwd-20260826xex991.htm). Exact statement-row and selected companyfacts reconciliation; discrepancy 0%.

Company statement (USD thousands): `Total revenue 1,305,375 1,058,538 4,812,005 3,953,624`. Columns: current quarter, prior quarter, current YTD/annual, prior YTD/annual. [SEC earnings release](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000007/crwd-20260303xex991.htm). Exact statement-row and selected companyfacts reconciliation; discrepancy 0%.

## Quarter path coverage

All ten current target quarters are loaded and quote-verified; seven implied-growth calculations pass and CRM/OKTA/S retain growth blocks. This is implementation coverage, not the Session 2 complete reconciliation audit. Each result preserves target boundaries, input IDs, policy, formula and growth review. Repeated guidance load and repeated quarter calculations inserted zero records.

Growth comparability and guidance-to-result comparability are independent. No current target-quarter result is yet reported, so all result-specific outcome reviews remain pending. Tests demonstrate a growth-blocked acquisition case can score within guidance when a separately evidenced, exact-version outcome review passes. No real live result is claimed.

## Date-source observations

Twenty individual observations are stored in session1-date-checks.json and referenced from companies.json. Successful observations have actual UTC fetched_at and hashes; failures retain checked_at and null fetched_at. No earlier timestamp was invented. Eighteen sources retrieved successfully; CrowdStrike and MongoDB official IR sources returned 403. Their earlier dated confirmations remain distinguished from the failed current rechecks. Salesforce and Okta confirmations were rechecked. Six exact upcoming dates and annual windows remain unverified/estimated.

## Environment, AGENTS and boundaries

The approved .venv directory is isolated, not a shared-venv symlink, and gitignored. Installed relevant dependency versions match requirements.txt, including psycopg and psycopg-binary 3.3.8. No dependency installation or shared environment change was needed. AGENTS.md is committed with its original SHA-256 269c885a42fcf425b8a03da0120e9aeb3190ca9a3e23ca42e42ffad83b6c51da. No apps/web, protected src, or 0001–0099 migration edits in this pass. Migration 0102 preserves existing RLS access conventions.

## Remaining work and stop

Quarterly target outcomes need future filed actuals and exact-version result-basis reviews. Current CRM, OKTA and S growth-comparison blocks remain unresolved. IR 403 gaps and unsupported exact dates are explicit. Experimental annual forecasts remain unvalidated and are not Session 3 baseline predictions or a live track record. Database-enforced immutable prediction locks remain absent. Stop for review before Session 2.
