# Scoring readiness and publication copy — November18 UTC

**Live ledger untouched:** eight existing predictions, zero results. Source access used READ ONLY transactions; before/after ledger SHA256 is identical: `8bca62620e2355b3151c73e0e3118681f1abbf03f8cae006c9e99e30a160dead`. No locks, source-row mutations, live scoring, backdating, inference, extraction review/tuning, merge, push or deployment. All Session3 tags and frozen code/schema remain unchanged. Pre-existing uncommitted announcement evidence updates are preserved separately and not included in this task's commit.

## What is actually frozen

| Rule | Frozen implementation | Readiness finding |
|---|---|---|
| Below/within/above | `engine.classify`: below `< low`; within includes both endpoints; above `> high`; point equality within | Implemented and tested |
| Multiclass Brier | `baseline.brier`, `score_live.evaluate`, migration0103 result guard: **unscaled** sum of three squared errors, range0..2 | Implemented; scratch pipeline and SQL reproduction passed |
| Log score | No formula, sign, zero rule, column or code in frozen METHODS/scorer/schema | **Missing; not silently added** |

For OKTA/IOT empirical0% below/within buckets, an unexpected below/within outcome has the existing finite Brier penalty (2 for a0/0/1 forecast). **The frozen system computes no log score.** Conventional `log(p_observed)` at zero is negative infinity; negative-log loss would be positive infinity. No clipping, epsilon, smoothing of the empirical locks, or new interpretation is authorized/applied. A future log metric requires an approved definition/version, including infinity handling and aggregation; it cannot pretend that rule existed at lock time. Laplace locks remain unchanged.

## Historical end-to-end scratch verification

[Complete six-case evidence](../validation/scoring_readiness_2026-11-18.json). Historical observations were taken from the separate source-table SQLite copy, not invented. Coverage-oriented selection deliberately chooses known below/within/above cases; each is replayed with the empirical and fixed add-one methods, respecting the original public-date historical selection rule. This is a scoring-mechanics test, **not fresh/held-out forecast performance, calibration evidence or a live track record**. Reviews are existing agent/source-curated history, not newly completed owner review.

The unchanged frozen source verifier, evaluator, saver and runner execute on TEMP actual/result tables and a TEMP view over labelled retrospective scratch inputs. No prediction table/record is created. Historical as-of values are selection coordinates in fixture payloads only; actual scratch creation/scoring times are PostgreSQL-generated now. The scratch namespace and SQL adapter prevent DML against live tables. The result guard body is copied unchanged to a private TEMP function; no public function/trigger is replaced. All scratch writes roll back/disappear on disconnect. Real SEC sources are re-fetched through the existing rate-limited fetcher.

Six method-cases scored across all three classes; repeating the run inserted zero duplicates. An incorrect in-range Brier was rejected by the copied frozen SQL guard. Endpoint and point-guidance checks, missing actuals, mismatched IDs/basis and non-prospective boundaries are additionally unit-tested. Current source-ledger integrity is independently rechecked after the rehearsal.

| Historical case | Reported revenue vs locked historical guidance | Outcome | Empirical Brier | Laplace Brier |
|---|---|---|---|---|
| LULU, May4–August2,2026 | $2,415,631,000 vs$2.450–2.475B | below |1.4693877551…|1.14|
| CRM, May1–July31,2026 | $11.345B vs$11.27–11.35B | within |0.6530612245…|0.62|
| ADBE, May30–August28,2026 | $6.760B vs$6.67–6.72B | above |0|0.06|

### Worked hand/code example: Salesforce historical Q2FY2027

This is **not** the currently locked Q3 target. Actual consolidated revenue **$11,345,000,000**, historical guidance **$11,270,000,000–$11,350,000,000**: within, because both endpoint comparisons pass. [Reported release, SEC0001108524-26-000187](https://www.sec.gov/Archives/edgar/data/1108524/000110852426000187/crm-q2fy27xexhibit991.htm); exact actual version, filing accession/date and source are preserved in the evidence JSON.

Seven eligible historical inputs at the retrospective coordinate yield counts below0/within3/above4. Hand empirical probabilities are `(0,3/7,4/7)`. For within, the Brier is `0²+(3/7−1)²+(4/7)² =32/49 ≈0.65306122449`. The frozen24-place probability convention gives within`0.428571428571428571428571` and residual above`0.571428571428571428571429`; code returns exactly **`0.653061224489795918367347918367346938775510204082`** from those stored inputs. The tiny difference from32/49 is the documented probability normalization, not display rounding or a changed formula.

Laplace uses `(0+1,3+1,4+1)/(7+3)=(0.1,0.4,0.5)`. Hand Brier is `0.1²+(0.4−1)²+0.5²=0.01+0.36+0.25=0.62`; code returns **`0.620000000000000000000000000000000000000000000000`**. Exact input observation/guidance/actual IDs, source accessions and timestamps are in the six-case artifact.

## Scoring-day procedure and remaining gates

[CURRENT_CHECKS.md](../CURRENT_CHECKS.md) now documents the Item2.02→Exhibit99.1 source relationship, consolidated revenue table/quarter/unit interpretation, exact companyfacts matching, owner outcome-basis review, earliest publication and day-precision availability, actual command, corrections and publication-copy refresh. [SCORING.md](../SCORING.md) provides the non-executable review field template and reproducible commands.

Important frozen limitation: earnings-release evidence alone is insufficient until the exact SEC companyfacts version exists and filing-day intervals have closed. Scoring may therefore occur after release night. Do not substitute zero, invent precision or backdate to avoid that block. Literal source matching does not establish semantic/table/basis correctness; owner review is mandatory. Prior-year growth acquisition blocks do not automatically decide guidance-to-result comparability; review the exact current actual/locked range separately.

No live score command was run. Future scoring requires genuine results and explicit owner authorization. Repeated actual evidence is idempotent; later corrections append linked versions rather than rewriting original results.

## Public predictions page

**Route: `/crosscheck/predictions`**. Local review server: **http://127.0.0.1:3108/crosscheck/predictions**. Launch normally from `apps/web` with `npm run dev` if that preview process has stopped. No deployment or browser automation.

Eight actual locked records are grouped into four companies with both methods, target quarter/exact boundaries, locked guidance range, DB lock timestamp, probabilities, evidence SHA256 and pending scheduled-results dates. Provenance remains expandable. After approved scoring and a manual copy refresh, the same page displays reported revenue, outcome vs locked range, exact Brier and correction-version count. Pending means no reviewed score in this copy, not proof that results are unpublished.

Data path: authenticated source **REPEATABLE READ / READ ONLY** export → separate ignored SQLite archive → sanitized committed `earnings/publication/predictions.json` → server-side file reader. **The route has no pg/DATABASE_URL/live-query dependency or fallback.** It served HTTP200 with an intentionally invalid `DATABASE_URL`, rendering exactly8 unique records; [HTTP evidence](../validation/public_predictions_route_2026-11-18.json). The evidence digest is computed for publication from immutable announcement/publication/snapshot inputs using the existing canonical hash function, not claimed as an externally notarized lock-time hash. Raw owner attestations/names stay out of public JSON; complete private copy remains ignored locally. Display financial arithmetic uses BigInt/string operations, not binary floats.

Black/silver styling is scoped to new CSS-module components. Only new `apps/web/src/app/crosscheck/predictions/**` and `apps/web/src/lib/crosscheck/predictions/**` files were added. Shared layout/navigation/global CSS, deals pages, dependencies, Tailwind/PostCSS and protected deals code were not modified. This page was explicitly authorized in the present request. No screenshot was taken under the no-browser-automation boundary; route/HTML, type and component tests passed. Visual compatibility remains unverified and required before merging. Coordinate route review with the deals agent before any later owner-controlled merge.

Tests: **66 Python tests passed,1 DB test skipped** with DATABASE_URL deliberately empty to prevent existing fixtures from inserting even rollback-only rows into the live ledger. **All29 frontend tests passed**, including6 new prediction-copy tests; TypeScript and scoped ESLint passed. The source-backed TEMP PostgreSQL rehearsal separately passed6 method-cases, duplicate repeatability and SQL Brier rejection. No production build/deployment claim; the route compiled and served through the existing local Next.js stack.

## Watchlist and preservation

[Six-company status and exact capture instructions](watchlist_2026-11-18.md), with timestamped direct-request records alongside it. GitLab's new November17 full official article verifies December1 afterclose in research; it is not imported/locked. CRWD/MDB direct original/PDF requests remain403; exact original capture links supplied. Adobe confirms a December9 call only. PagerDuty/lululemon remain unverified, not “not announced.” No other-company probabilities or dates were fabricated/promoted.

All frozen tags/code/schema preserved; [final integrity evidence](../validation/scoring_publication_integrity_2026-11-18.json) shows identical live-ledger hashes before/after,8 predictions/0 outcomes. Extractor remains shelved, owner extraction review deferred/not performed, fresh evaluation untouched. No provider calls;$8 ceiling and$2.2373935 unresolved holds unchanged, occupancy$2.6009185. No push, merge, deployment or new locks.
