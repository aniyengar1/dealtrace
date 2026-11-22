# Final bounded rule-only repair review — November 13, 2026 UTC

**V2 meets the numerical fresh-sample thresholds: 100% strict precision, 90% recall (18 emitted records, 20 gold).** This is a small-sample result, not a claim of general 98% precision or production readiness. No further tuning followed the single fresh evaluation. Session 5 remains blocked for review. Session 3’s prospective live gate remains pending.

## Immutable checkpoints and evaluation credibility

- `session3-lock-ready` remains **94984fc3ce33c6e85a287738d3a617561cd0cefc**; never moved.
- **18ef3b1**: new release reservation and selection procedure committed before rule edits.
- **19cfaa5**: all v2 rule/pipeline/corpus/scoring implementation frozen before reserved release bodies were opened or gold was curated.
- **bef0fbb**: independent-of-extractor manual gold committed before its first evaluation.
- Original v1 split, frozen rules, gold, outputs and reported scores remain unchanged. Its former holdout is now diagnostic data. Fifteen original v1 artifacts were hash-checked against f1a9d73, and all match.

Reservation: one original Item 2.02 earnings release per existing issuer, selected as the latest filed April–July 2023, with the immediately preceding earnings release reserved as context. All related versions/exhibits stay in their issuer group, never development data. No selection by extraction success. An initial metadata-only 2024 proposal was rejected before body inspection to avoid annual-period overlap with exposed later guidance. Exact accession/filing inventory and the procedure are in `earnings/extraction/v2/reservation.json`.

The ten evaluation documents and ten context documents were retrieved only after v2 freeze, through the existing SEC fetcher. Gold was manually transcribed from all relevant source target statements, not selected from candidate outputs. Decimal scaling, literal datelines/quotes, retained body hashes and fiscal-calendar boundaries were separately verified (`session4_repair_fresh_gold_verification.json`: 20/20). Table headings/units and context were manually inspected. Quote checking does not by itself prove semantic correctness. There is one curator and no second independent human adjudicator. The author knew these issuers/later formats and had seen historical companyfacts; the 2023 release bodies and target periods were not development examples. This is fresh-period evaluation, not blind unseen-issuer evaluation.

Gold has 20 labels, two per evaluation document. Quarterly initial status means the first direct range observed in the reserved group; `original_verified=false` avoids claiming exhaustive original-guidance history. Context supports revisions but is not in target recall. Gold SHA-256: `cf19649ba9f901bf8245410a3d844f407998c835584bbb4599c83b44a7bc7e4c`. No gold labels changed after evaluation.

## Strict scores

| Set | Correct / emitted / gold | Precision | Recall | Wrong emitted records | Missing/abstained gold |
|---|---|---|---|---|---|
| Development | 89 / 89 / 96 | 100.00% | 92.71% | 0 | 7 |
| Former holdout: diagnostic only | 33 / 33 / 38 | 100.00% | 86.84% | 0 | 5 |
| Fresh reserved releases: once | 18 / 18 / 20 | 100.00% | 90.00% | 0 | 2 |

The original v1 scores remain development 98.95%/97.92% and old holdout 47.92%/60.53% precision/recall. The repaired old-holdout score above is regression performance, **not fresh held-out improvement**. Old gold uses the original positive-only document+metric evaluation scope; fresh releases were exhaustively reviewed for annual/direct-next-quarter revenue, and all candidate outputs in those documents count. Unjudged old document+metric outputs remain reported separately rather than assumed correct.

## Per-company results

Each cell is strict correct/emitted/gold, then precision/recall. No company was dropped for poor results.

| Company | Development | Former-holdout diagnostics | Fresh evaluation |
|---|---|---|---|
| ADBE | 12/12/13; 100.00%/92.31% | — | 1/1/2; 100.00%/50.00% |
| CRM | 13/13/13; 100.00%/100.00% | — | 2/2/2; 100.00%/100.00% |
| CRWD | — | 11/11/12; 100.00%/91.67% | 2/2/2; 100.00%/100.00% |
| GTLB | 15/15/16; 100.00%/93.75% | — | 2/2/2; 100.00%/100.00% |
| IOT | — | 11/11/12; 100.00%/91.67% | 2/2/2; 100.00%/100.00% |
| LULU | — | 11/11/14; 100.00%/78.57% | 1/1/2; 100.00%/50.00% |
| MDB | 13/13/15; 100.00%/86.67% | — | 2/2/2; 100.00%/100.00% |
| OKTA | 12/12/13; 100.00%/92.31% | — | 2/2/2; 100.00%/100.00% |
| PD | 13/13/14; 100.00%/92.86% | — | 2/2/2; 100.00%/100.00% |
| S | 11/11/12; 100.00%/91.67% | — | 2/2/2; 100.00%/100.00% |

## Fields, abstentions and observed repairs

No emitted record in any of these three evaluations had a strict field mismatch. Abstentions still count against recall; they are not removed from the gold denominator. Supplied SEC filing/accession/exhibit metadata and manually registered calendar/basis conventions must not be described as learned extraction successes.

| Field | Development correct / gold | Diagnostic correct / gold | Fresh correct / gold |
|---|---|---|---|
| accession | 89/96 | 33/38 | 18/20 |
| basis | 89/96 | 33/38 | 18/20 |
| end | 89/96 | 33/38 | 18/20 |
| exhibit | 89/96 | 33/38 | 18/20 |
| filed | 89/96 | 33/38 | 18/20 |
| high | 89/96 | 33/38 | 18/20 |
| issued | 89/96 | 33/38 | 18/20 |
| low | 89/96 | 33/38 | 18/20 |
| metric | 89/96 | 33/38 | 18/20 |
| start | 89/96 | 33/38 | 18/20 |
| status | 89/96 | 33/38 | 18/20 |
| unit | 89/96 | 33/38 | 18/20 |

- ARR/non-consolidated metric rows are excluded before any amount can enter revenue history. New normal tests demonstrate no ARR poisoning; the original frozen-v1 ARR test remains an expected failure.
- Direct and implied table columns retain separate headings and values. Derived columns are explicitly rejected without shifting later direct columns or creating Q4 history. The old frozen-v1 implied-column test remains an expected failure; a separate v2 test passes.
- Prose fiscal context is kept local. Ambiguous mixed quarterly/annual clauses abstain. Status history keys require identical company/metric/fiscal bounds/basis/unit, non-future sources and directly issued revenue evidence. Source IDs and exact before/after ranges support revisions.
- Unresolved annual initial/revision status becomes a review partial. Explicit qualitative references require a compatible earlier range; missing references do not invent numbers or a status.

Raw abstention counts include rejected ARR and unjudged contexts; they are **not** the number of missed gold labels. The target-level misses below explain the recall cost.

| Set / issuer | Missed gold and source | Reason / evidence gap |
|---|---|---|
| Development / ADBE | `b7c14351-ad44-5757-b7f8-b816b58002ff`, consolidated_revenue 2025-11-29–2026-11-27, USD 25900000000.00–26100000000.00, initial; [SEC 0000796343-25-000135](https://www.sec.gov/Archives/edgar/data/796343/000079634325000135/adbeex991q425.htm) | Unresolved initial/revision annual status history; partial withheld |
| Development / GTLB | `0b4891ac-f765-5fb8-a0cb-39130819cb06`, consolidated_revenue 2026-02-01–2027-01-31, USD 1099000000–1118000000, initial; [SEC 0001628280-26-013795](https://www.sec.gov/Archives/edgar/data/1653482/000162828026013795/gitlab-ex99120260131fy26.htm) | Unresolved initial/revision annual status history; partial withheld |
| Development / MDB | `3f519fed-b8c0-526f-838f-f91a1fedcd8c`, quarterly_consolidated_revenue 2025-11-01–2026-01-31, USD 665000000.0–670000000.0, initial; [SEC 0001628280-25-054569](https://www.sec.gov/Archives/edgar/data/1441816/000162828025054569/a8-kaexhibit991revised.htm) | Unsupported/ambiguous flat or qualitative source context; abstained |
| Development / MDB | `7c6457c8-02c2-5d4f-8e62-43c1654db87c`, consolidated_revenue 2026-02-01–2027-01-31, USD 2860000000.000–2900000000.000, initial; [SEC 0001628280-26-013199](https://www.sec.gov/Archives/edgar/data/1441816/000162828026013199/mdb-13126xex991xrelease.htm) | Unresolved initial/revision annual status history; partial withheld |
| Development / OKTA | `c070d7c9-4e74-5c1c-a790-ff98b6b9d38b`, consolidated_revenue 2026-02-01–2027-01-31, USD 3170000000.000–3190000000.000, initial; [SEC 0001660134-26-000016](https://www.sec.gov/Archives/edgar/data/1660134/000166013426000016/okta-1312026_ex991.htm) | Unresolved initial/revision annual status history; partial withheld |
| Development / PD | `a2aed39a-a88c-5b65-91e8-0bf81f743819`, consolidated_revenue 2026-02-01–2027-01-31, USD 488500000–496500000, initial; [SEC 0001568100-26-000011](https://www.sec.gov/Archives/edgar/data/1568100/000156810026000011/ex991-pagerdutyq4fy26earni.htm) | Unresolved initial/revision annual status history; partial withheld |
| Development / S | `9d5b2b30-61e6-57cd-b6fc-39a0905bb865`, consolidated_revenue 2026-02-01–2027-01-31, USD 1195000000.000–1205000000.000, initial; [SEC 0001583708-26-000014](https://www.sec.gov/Archives/edgar/data/1583708/000158370826000014/sentineloneq426exhibit991.htm) | Unresolved initial/revision annual status history; partial withheld |
| Former holdout: diagnostic only / CRWD | `6a52f11e-61b8-554e-826f-4dc433be1b18`, consolidated_revenue 2026-02-01–2027-01-31, USD 5867600000.0000–5927600000.0000, initial; [SEC 0001535527-26-000007](https://www.sec.gov/Archives/edgar/data/1535527/000153552726000007/crwd-20260303xex991.htm) | Unresolved initial/revision annual status history; partial withheld |
| Former holdout: diagnostic only / IOT | `2824c751-b7ba-52a9-a9af-1b995d6933ac`, consolidated_revenue 2026-02-01–2027-01-30, USD 1965000000.000–1975000000.000, initial; [SEC 0001628280-26-015170](https://www.sec.gov/Archives/edgar/data/1642896/000162828026015170/samsaraepr-q42026.htm) | Unresolved initial/revision annual status history; partial withheld |
| Former holdout: diagnostic only / LULU | `428042f8-d727-51ae-9c58-b562f949a824`, quarterly_consolidated_revenue 2024-10-28–2025-02-02, USD 3560000000.000–3580000000.000, raised; [SEC 0001397187-25-000004](https://www.sec.gov/Archives/edgar/data/1397187/000139718725000004/lulu-20250113xex991.htm) | Unsupported/ambiguous flat or qualitative source context; abstained |
| Former holdout: diagnostic only / LULU | `97e0b842-2159-5e01-9e6f-c0e00779a660`, consolidated_revenue 2026-02-02–2027-01-31, USD 11350000000.000–11500000000.000, initial; [SEC 0001397187-26-000019](https://www.sec.gov/Archives/edgar/data/1397187/000139718726000019/lulu-20260201xex991.htm) | Unresolved initial/revision annual status history; partial withheld |
| Former holdout: diagnostic only / LULU | `922c08aa-ed21-56eb-8898-fe746b19f388`, consolidated_revenue 2026-02-02–2027-01-31, USD 10350000000.000–10500000000.000, lowered; [SEC 0001397187-26-000126](https://www.sec.gov/Archives/edgar/data/1397187/000139718726000126/lulu-20260802xex991.htm) | Unresolved initial/revision annual status history; partial withheld |
| Fresh reserved releases: once / ADBE | `7f177d08-28e8-5c94-bda3-f04ba84c3de4`, consolidated_revenue 2022-12-03–2023-12-01, USD 19250000000.00–19350000000.00, raised; [SEC 0000796343-23-000133](https://www.sec.gov/Archives/edgar/data/796343/000079634323000133/adbeex991q223.htm) | June source explicitly raises annual revenue, but immediately preceding March context updates ARR/EPS only and supplies no annual revenue range. V2 does not resolve the raise from the headline alone. |
| Fresh reserved releases: once / LULU | `9dd05523-5fdc-5c51-9c54-b87d3a64e8d0`, consolidated_revenue 2023-01-30–2024-01-28, USD 9440000000.000–9510000000.000, raised; [SEC 0001397187-23-000026](https://www.sec.gov/Archives/edgar/data/1397187/000139718723000026/lulu-20230430xex991.htm) | The preceding “For fiscal 2023, we expect” annual context was not parsed. Current annual amount/period are captured as a partial, but status remains unresolved. |

The fresh Adobe and lululemon ranges are supported by company evidence and can be labeled by a curator. These are parser limitations, not claims that the companies failed to supply guidance. Withholding them reduces fresh recall by 10 percentage points. No rule or gold change was made to recover those two records after inspection.

Full per-record candidates, partials, abstention reasons, source hashes, primary-document date evidence, source quotes/table context and input-edge IDs are in the three evaluation JSONs. Candidate quotes retain exact canonical Unicode offsets and raw/canonical hashes. The original manual guidance files and live input records are unchanged.

## Final-pass stopping rule

Fresh strict precision 1.00 is not below 0.98 and recall 0.90 is not below 0.90. Therefore the conditional instruction to stop and write an LLM/hybrid proposal on a failed fresh threshold was **not triggered**. No LLM/hybrid implementation or inference calls were made, and no shared model quota was consumed. This final rule-only pass is stopped for review; it is not authorization for another repair cycle.

Eighteen correct emitted records provide too little evidence for a general 98% precision guarantee. Familiar-issuer templates, one curator, only one target release per issuer, first-observed rather than exhaustive original-guidance history, and remaining diagnostic recall below 90% limit the result. No production promotion or Session 5 is implied by meeting the point-estimate thresholds. An architecture review may still be appropriate; any eventual LLM use requires explicit approval and shared-quota coordination first.

## Session 3 protection and actual-clock dry run

All **64 protected code/data/schema files**, the installed dependency freeze and **15 original v1 artifacts** are unchanged. The local Session 3 tag retains its exact target. New extractor files are not imported by the lock workflow. The preserved isolated tag archive and HEAD produced identical fixed-input/time outputs across outside/inside windows, exact deadlines, withdrawal, staleness, already-public results and missing history. Eligibility, guidance/target IDs, historical input IDs, probabilities, method and rejection reasons match exactly. These synthetic proposals are not live predictions.

Both actual-clock dry runs used PostgreSQL READ ONLY with history ingestion and ledger insertion suppressed, checked required migrations and rolled back. Differences are only their real execution timestamps.

| Code | Actual UTC execution | READ ONLY | Ledger before -> after | Result |
|---|---|---|---|---|
| tag | 2026-11-13T04:33:47.265174+00:00–2026-11-13T04:33:47.278032+00:00 | on | 0 -> 0 | 0 locks; 4 outside window, 6 unverified |
| head | 2026-11-13T04:33:47.504866+00:00–2026-11-13T04:33:47.520432+00:00 | on | 0 -> 0 | 0 locks; 4 outside window, 6 unverified |

No backdated or out-of-window prediction exists. Session 3’s live gate stays pending. Next manual date-only windows open at **00:00 America/New_York / 05:00 UTC**: OKTA November 17 (deadline December 1 start), CRM November 18 (December 2 start), IOT/S November 19 (December 3 start). All actual locks require fresh announcement and already-public-results checks; after-close wording never permits a 16:00 deadline. CRWD/MDB/ADBE/PD/GTLB/LULU remain timing-unverified. Nothing is automatically scheduled.

## Verification and run instructions

Complete suite: **394 passed, 3 skipped, 2 xfailed**. The two xfails are unchanged frozen-v1 tests, not repaired behavior being counted as passing. Eight normal behavior tests plus two freeze/abstention tests cover v2. No production prediction code, data, database schema, model policy, dependency version, website or deals functionality changed.

```sh
.venv/bin/python -m earnings.extraction.v2.verify_gold --output /tmp/repair-gold-new.json
.venv/bin/python -m earnings.extraction.v2.evaluate --dataset development --output /tmp/repair-development-replay.json
.venv/bin/python -m earnings.extraction.v2.evaluate --dataset old-heldout-diagnostic --output /tmp/repair-diagnostic-replay.json
.venv/bin/python -m earnings.extraction.v2.evaluate --dataset fresh --output /tmp/repair-reserved-set-replay.json
.venv/bin/python earnings/lock_ready/check.py --code-root . --output /tmp/repair-lock-readonly-new.json
.venv/bin/python -m pytest -q
```

Output paths must be new. After the first reserved-set evaluation, the `fresh` CLI argument names that fixed dataset; later executions are replays, not new fresh held-out evidence. No candidates are loaded into production guidance. **Stop for review; no Session 5, LLM calls, website changes, merge, push or deployment.**
