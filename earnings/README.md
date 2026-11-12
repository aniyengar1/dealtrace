# Crosscheck

Crosscheck measures the revenue required to meet annual company guidance. It uses manual SEC-backed guidance, SEC companyfacts, Decimal arithmetic, content-versioned financial records, and explicit as-of dates. The current milestone adds a ten-company search and overview interface plus an **experimental annual revenue forecast**. A Q3 report updates the annual hurdle; only an annual result can resolve an annual guidance outcome.

## Launch search → overview → targets → forecast → evidence

The interface uses the existing Next.js app at `/crosscheck`. Its server reads content-versioned PostgreSQL reports produced by the Python earnings pipeline. All financial math stays in Decimal; JSON financial amounts remain strings, including in the browser. The existing deals query layer is reused only for server-side database access. New routes expose reads, not writes.

From the repository root, using the worktree-specific environment:

```sh
.venv/bin/python -m earnings migrate
.venv/bin/python -m earnings.product refresh ALL --as-of 2026-11-11 --verify-guidance
```

In a separate terminal:

```sh
cd apps/web
npm ci
npm run build -- --webpack
npm run start -- --hostname 127.0.0.1 --port 3011
```

Open `http://127.0.0.1:3011/crosscheck`. For development, use `npm run dev -- --webpack --hostname 127.0.0.1 --port 3011`. The Webpack flag is intentional: this environment denies the local helper-port binding used by Turbopack's CSS worker, including during a production build. The pinned official Tailwind PostCSS plugin compiles the same utilities for the supported Webpack path. The existing Turbopack configuration remains unchanged.

Search by name or ticker, then open a company. The page shows the exact research cutoff, financial periods, filing dates, manual freshness state, guidance history, required performance, experimental revenue forecast, and expandable source/record details. Unsupported companies have an explicit coverage view and a 404 JSON response. A date without a calculated snapshot shows a missing-report state; an earlier snapshot is never silently substituted. The default is the latest published cutoff no later than today, **not a claim of live data**. A later cutoff requires a new refresh.

Read-only evidence JSON: `/api/crosscheck/PD?asOf=2026-11-11`. API financial values retain their Decimal strings. Public read/service-role write RLS applies to both new tables, `earnings_metric_facts` and `earnings_company_reports`, matching the earnings/deals conventions. Database credentials stay server-side.

### Forecast method and validation status

`seasonal-ytd-growth-v1-decimal50` calculates:

```
observed_growth = current_YTD / prior_corresponding_YTD - 1
forecast = current_YTD + prior_remaining * (1 + observed_growth)
benchmark = current_YTD + prior_remaining
```

The point forecast carries observed YTD growth into the prior-year remaining seasonal period. Guidance affects the beat/meet/miss classification, not the numerical estimate. For point guidance, exact equality is meet; below is miss and above is beat, with no implicit tolerance. It assumes stable seasonality and recent growth; it does not model future inflections, quarterly outlooks, acquisitions, or currency changes. Forecast inputs and formula/policy versions are preserved with the underlying hurdle's exact record IDs. No other displayed metric has a forecast in this milestone. There is no consensus data connection.

The forecast is **not validated for general use**. One manually reviewed historical case is available: PagerDuty FY2026, forecast at September 4, 2025 using six-month YTD inputs. Earliest reported annual revenue is the outcome. Baseline absolute error is $8.113M (1.65%); the flat-growth benchmark error is $8.938M (1.81%). The baseline called **beat**, but the reported result **missed** the range known at the forecast date: classification 0/1. One example cannot establish skill, and is not representative of every company or forecast horizon (Adobe currently uses nine-month YTD). No probabilities, confidence labels, or prediction intervals are supported or published.

GitLab's earlier FY2026 backtest is excluded because Oxeye's March 2024 acquisition creates a pre-acquisition interval in the prior YTD. That historical exclusion does not reverse the separately reviewed current FY2027 calculation. Other companies require historical guidance, scope, and/or fiscal-calendar review before joining the evaluation cohort. Coverage is reported as reviewed companies out of the ten supported companies, not as an accuracy claim.

```sh
.venv/bin/python -m earnings.product evaluate --as-of 2026-11-11
```

Evaluation cases are explicit in `evaluation_cases.json`. All forecast inputs and scope sources must be public by their historical forecast cutoff. Later filings, guidance, and restatements are excluded from inputs; the earliest reported annual outcome is selected separately, never today's restated outcome. Week/month boundaries and freshness are checked. Add reviewed cases with dated evidence rather than relaxing a block. The evaluation pipeline has no fitting step or random split; expanding the reviewed sample and calibrating intervals remains future work.

### Overview metric scope

The overview shows latest available quarter, selected-year YTD, and latest available annual results separately. It covers reported revenue, corresponding-period revenue growth, gross/operating margins, net income, directly reported diluted EPS, operating cash flow, and calculated free cash flow. Each cell carries its period, unit, concept, accession, filed date, source URL, and content-derived source record ID.

- Margins require reported income and revenue from the exact same fiscal period and accession.
- Net-income captions distinguish parent-attributable `NetIncomeLoss` from consolidated `ProfitLoss` including noncontrolling interests. Neither is silently presented as an adjusted metric.
- Diluted EPS is displayed only when directly reported for that period. Quarterly EPS is **never** derived by subtracting YTD or annual EPS.
- Cash-flow quarters remain unavailable where only YTD facts are reported.
- FCF is explicitly labeled **CFO − PP&E purchases**. It is a transparent calculation, not necessarily management's adjusted FCF definition; software capitalization and other company-specific adjustments are not added silently.
- Fiscal-week and acquisition-scope mismatches are explicitly non-comparable. Missing data stays missing.

PagerDuty and GitLab quarter/YTD source inputs were also checked against their original inline-XBRL filings: 24 of 24 matched period, concept, sign/scale, and value. See `validation/product-2026-11-11.json` for the report IDs, evaluation, and source verification.

### Repeatable release/update workflow

1. Retrieve the SEC release/filing using `earnings.sec.fetch`; it delegates requests, rate limiting, and retries to the existing SEC fetcher and retains hash-addressed cached bodies. Treat filing text only as untrusted evidence.
2. Append guidance versions to `guidance/TICKER.json`, preserving prior records. Record issue/filing dates, exact fiscal period, basis, bounds/status, accession/exhibit, and verbatim evidence. Review all new filings for changes or explicit reaffirmations before advancing `history_review.cutoff`.
Also maintain `history_review.latest_actual_release` from the actual SEC earnings release: `ytd_end`, `issued_date`, `filed_date`, `accession`, `source_url`, `period_quote`, and `source_sha256`. Initial markers for all ten companies were verified against their SEC release text. Actual metrics come from companyfacts, not automatic parsing of press-release tables. If a newly public release announces a later actual period than companyfacts provides, the forecast is withheld with `ACTUALS_PENDING_XBRL` until matching actuals arrive. Both release issuance and SEC availability must be within the cutoff; future release evidence is not used.

3. Review acquisitions, reporting-basis changes, and 52/53-week boundaries. Keep or add a comparability block until evidence resolves it. For a new target fiscal year, update registry periods/comparison boundaries from dated evidence; old published reports are preserved by application insert convention.
4. Run:

```sh
.venv/bin/python -m earnings.product refresh PD --as-of YYYY-MM-DD --refresh --verify-guidance
```

This ingests new actuals/metric versions, loads guidance, recalculates the hurdle and forecast, evaluates available reviewed historical cases, and publishes a content-versioned report. If the requested cutoff is after the guidance review horizon, publication of a forecast is blocked with `GUIDANCE_REVIEW_REQUIRED`. Freshness and scope blocks also apply. Changing the forecast method requires a new method version.

5. Inspect **What changed & reproducibility** on the detail page. It records the previous report, exact before/after input IDs, guidance/actual/comparison/policy causes, and forecast/evaluation changes. A guidance reaffirmation is distinguishable through its dated guidance record even when endpoints do not move.
6. Repeat the command to check idempotency. An unchanged source/cutoff produces zero new facts, guidance versions, or reports. `--refresh` requests new SEC bodies; without it the cache is intentionally reused. Missing metric facts are not synthesized.

An inaccessible source or failed company update creates a sanitized JSON gap under `data/cache/earnings/update-gaps/` and a machine-readable stdout result; other companies continue. No replacement report is fabricated, old snapshots keep their original cutoffs, and the batch exits nonzero if any update fails. A failed URL is recorded only when available from request metadata, otherwise left unknown rather than guessed. A transaction rollback prevents a partially published company update.

### Verify without browser automation

```sh
.venv/bin/python -m pytest -q
cd apps/web
npm test
npx tsc --noEmit
npm run lint
npm run build -- --webpack
```

With the built app running on port 3011, from the repository root:

```sh
.venv/bin/python -m earnings.smoke --base-url http://127.0.0.1:3011
```

The read-only smoke command checks the real index, all ten company detail pages and JSON reports, the three comparison blocks, unsupported MSFT, an unpublished cutoff, and an invalid date. It uses direct local HTTP and server-rendered HTML, not Chrome or browser automation. Component tests cover loading, sanitized errors, stale blocks, missing cutoffs, name/ticker filtering, unsupported coverage, and exact Decimal-string API responses. It does not claim visual/pixel QA.

## Phase 1 source pipeline

Run from the earnings worktree on branch `earnings`. Use an isolated environment; never modify the deals agent's environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m earnings migrate
.venv/bin/python -m earnings verify-guidance ALL
.venv/bin/python -m earnings ingest PD GTLB
.venv/bin/python -m earnings load-guidance PD GTLB
.venv/bin/python -m earnings calculate PD GTLB --as-of 2026-11-11
.venv/bin/python -m earnings verify-real PD GTLB
```

`DATABASE_URL` is loaded with python-dotenv; no host/database names are hardcoded. Use a binary PostgreSQL driver. `migrate` uses the existing migration runner and applies **all** pending repository migrations, so inspect the pending filenames when sharing a database. Earnings migrations start at 0100; deals migrations 0001–0099 are protected.

Extend the same workflow to all ten approved companies:

```sh
.venv/bin/python -m earnings ingest ALL
.venv/bin/python -m earnings load-guidance ALL
.venv/bin/python -m earnings calculate ALL --as-of 2026-11-11
.venv/bin/python -m earnings report-dates ALL --as-of 2026-11-11
.venv/bin/python -m earnings inspect CALCULATION_UUID
.venv/bin/python -m earnings inspect INPUT_RECORD_UUID
.venv/bin/python -m earnings compare EARLIER_CALCULATION_UUID LATER_CALCULATION_UUID
```

`ingest` and `load-guidance` insert zero records on an unchanged repeat. Pass `ingest --refresh` to check for new SEC facts; otherwise the existing cache is intentionally reused. Every refreshed body and hash manifest is retained under gitignored `data/cache/earnings/`. All SEC transport uses `src.fetch`'s request/retry/rate logic; a Crosscheck process lock shares its limiter timestamp between concurrent Crosscheck commands. The module does not control a separate deals process's requests.

Actuals preserve every accession/filed-date/value/fiscal-label version, including amendments. Frame labels are not used to infer quarters. IDs are deterministic UUIDs derived from canonical record contents, and act as immutable content versions. Identical duplicate companyfacts observations collapse; conflicting values filed on the same day block selection. Historical selection chooses the latest public version **within the cutoff**, never the latest version today.

## Guidance and evidence

`companies.json` is the approved provisional registry and selected consolidated US-GAAP revenue concept per company. Each `guidance/TICKER.json` contains the original and reviewed subsequent versions through November 11, 2026, source accession/exhibit, issued and filed dates, period, metric, dollar bounds, basis, status, and a verbatim quote. `history_review.sources_reviewed` records the review scope. No withdrawal/reinstatement was identified in these selected-year histories; both statuses are implemented and tested.

Explicit reaffirmations can incorporate prior guidance by reference; copied bounds retain the prior dollar-range evidence in the same history. A reaffirmation is a version, even if its endpoints do not change. A presentation that merely repeats an old range does not reset freshness. MongoDB's September 29 presentation explicitly disclaims reaffirmation; its September 28 press release does reaffirm. Salesforce's October 20 statement of no anticipated guidance change is recorded with its unchanged August bounds and remains acquisition-blocked.

`verify-guidance` checks the quote against the SEC document and reports its SHA-256. This is a quote-presence check, **not automatic certification of the manual numerical interpretation**. The initial two-company reconciliation also independently checks the reported statement columns, their thousands-to-dollars scale, and companyfacts-derived hurdle amounts. `verify-real` reproduces the fixed November 11 reconciliation in `reconciliation.json`; it is not an arbitrary-date validation command.

Financial evidence remains SEC-only. The approved exception allows official company IR sources **only for earnings announcement dates**. Registry dates distinguish a dated confirmed announcement, an unverified exact date, and a historical estimated window. No third-party calendar is used. `report-dates --as-of` hides announcements not yet public by the cutoff. The expected annual-result windows are estimates, not commitments: Salesforce February 2027; the other January-ending companies March 2027; Adobe December 2026. Adobe's next expected release is Q4/FY; the other nine are Q3 hurdle updates.

## Calculation and historical rules

```
remaining_low  = guidance_low  - actual_ytd
remaining_high = guidance_high - actual_ytd
growth_low     = remaining_low  / prior_year_remaining - 1
growth_high    = remaining_high / prior_year_remaining - 1
```

All financial parsing and arithmetic uses Decimal. Division uses a versioned 50-significant-digit context; no display quantization is applied to stored results. Recurring decimals necessarily have finite context precision. JSON financial values are decimal strings; database amounts and ratios are NUMERIC without a fixed display scale.

The prior remaining period is prior annual revenue less prior matching YTD, with exact entity/concept/basis/unit and fiscal boundary checks. Month-based fiscal boundaries must correspond; a leap day alone does not change a month-based quarter. Week-based years must match YTD and remaining week counts. A 53-week Q4 can be derived as 14 weeks, but the hurdle blocks comparison with a 13-week Q4 rather than normalizing it. `derive_q4` requires explicit nine-month and year-end boundaries and rejects other YTD lengths. Missing inputs stay missing.

Every calculation stores the formula version, full manual freshness policy, the financial registry configuration used, and exact guidance/YTD/prior-annual/prior-YTD/derived-remainder input IDs. Derived actuals also retain parent edges. `compare` attributes version changes to guidance, actuals, prior comparison, comparability review, and policy/freshness changes; guidance attribution includes explicit reaffirmations, not just changed dollar bounds. Announced report dates are not financial calculation inputs.

Freshness policy **manual-freshness-v1** is a research assumption, **not an accounting standard**:

- Actuals become stale when the cutoff is **more than 135 days after the latest YTD period end**.
- Guidance becomes stale when the cutoff is **more than 150 days after its latest explicit issuance/reaffirmation**.
- Exactly 135/150 days passes. Imprecise issuance intervals use the earliest possible day for a conservative age check; public availability requires the interval's end and filing date to be within the cutoff.
- A stale result retains input references and states each triggering age/threshold in `details`.

For different thresholds, use a new policy version:

```sh
.venv/bin/python -m earnings calculate PD --as-of 2026-11-11 \
  --actual-days 120 --guidance-days 140 --policy-version manual-freshness-v2
```

Blocking/review codes are `MISSING_PERIOD`, `INCOMPARABLE_BASIS`, `ZERO_DENOMINATOR`, `NEGATIVE_RESIDUAL`, `GUIDANCE_WITHDRAWN`, and `STALE_INPUT`. Negative residuals retain their signed amounts and growth rates and require review. Blocking inputs are never replaced by zero. If an annual fact is already public, use outcome classification rather than an active hurdle.

## Annual outcomes

The first **verified** valid annual range is the original benchmark. Missing original evidence blocks the original comparison with `ORIGINAL_GUIDANCE_UNAVAILABLE`; a later range is never substituted. The latest benchmark is the last eligible guidance before the annual-result announcement, or an earlier public annual filing. A later 10-K does not move that benchmark cutoff. The SEC filing date of the result-release evidence must also be within the outcome cutoff. Day-only guidance on the result date is conservatively excluded because intraday ordering is unknown.

After annual results and their SEC actuals are public:

```sh
.venv/bin/python -m earnings outcome PD --as-of YYYY-MM-DD \
  --result-issued YYYY-MM-DD --result-filed YYYY-MM-DD --result-accession SEC_ACCESSION \
  --result-url https://www.sec.gov/Archives/edgar/data/.../earnings-release.htm
```

`--result-issued` also accepts a JSON `{start,end,precision}` interval. The operator supplies the actual dated annual earnings-release evidence, not an estimated calendar date. The command refuses a missing annual fact; it never treats Q3 as the annual outcome. Pass `--not-comparable` for a newly identified material change; separate outcome comparability reviews apply; a growth-comparison block alone does not decide scoring. Endpoint equality is `within`.

Withdrawal blocks active hurdles without deleting the initial range. A comparable original-guidance outcome remains possible and is labeled subsequently withdrawn. During an unresolved withdrawal, the latest comparison has no outcome and carries `GUIDANCE_WITHDRAWN`. Reinstatement restores a latest benchmark without resetting the original. Material basis changes yield `not_comparable`.

## Current limitations and review blocks

- Salesforce: Informatica and Contentful/Fin scope, plus the later Braze announcement, require evidence reconciliation. Its annual companyfacts fiscal-year label is inconsistent with its period boundaries; raw labels are preserved.
- Okta: Permiso's August acquisition is a subsequent event with consideration under evaluation; guidance/comparison scope is unresolved. The professional-services partner shift is disclosed.
- SentinelOne: Prompt/Observo create different ownership durations in the comparison periods; revenue effects have not been reconciled.
- Adobe, MongoDB, and CrowdStrike: as-reported figures include acquisitions their filings explicitly describe as not materially affecting the financial statements. This is documented in the registry; **no organic or pro-forma normalization** is performed. Revisit if later evidence changes that assessment.
- Financial guidance histories and registry reviews are manually maintained through the stated cutoff. New filings require refresh, evidence review, and new guidance versions/configuration where needed. No claim of automatic guidance discovery or an exhaustive audit beyond the documented SEC review scope is made.
- Six exact next-report dates remain unverified. Annual windows remain estimated. There are no live annual outcomes yet for these selected fiscal years.

## Tests and audit snapshot

```sh
.venv/bin/python -m pytest tests/earnings -q
```

Tests use the existing real-PostgreSQL session migration/per-test rollback convention. They cover blueprint arithmetic; zero/negative/missing inputs; withdrawal/reinstatement; as-of revisions; inclusive outcomes; 52/53-week and basis mismatches; threshold boundaries; version preservation and repeat ingestion; relational provenance; cross-company constraints; cache integrity; and public read-only/service-role writes.

`validation/2026-11-11.json` contains all ten calculation records, exact selected input versions and source links, guidance quote verification, initial statement reconciliation, and reporting-date metadata. It is a review snapshot, not an ML prediction or annual scoring record. Recreate inputs using the commands above; inspect stored IDs for the original content-versioned calculation even after later filings arrive. That Phase 1 snapshot predates the interface/forecast milestone above. Protected src files, the shared venv, and deals migrations remain unchanged.


## Bounded Session 1 completion (November 11, 2026)

This pass adds **quarterly consolidated revenue guidance**, not the Session 3
probabilistic baseline or live prediction ledger. Existing annual forecasts remain
experimental and unvalidated. Existing interface work is preserved; this pass
makes no website changes. The Session 2 full-universe audit has not been started.

### Setup and boundaries

The approved environment is the real, gitignored worktree directory `.venv/`,
not a symlink into Claude's environment. Create/install using the root setup
commands above. `requirements.txt` pins requests 2.34.2, beautifulsoup4 4.15.0,
lxml 6.1.3, python-dotenv 1.2.4, psycopg[binary] 3.3.8 and pytest 9.2.0;
`pip check` passes. The driver includes psycopg-binary 3.3.8. No shared environment
or dependency file was modified in this pass. AGENTS.md is committed unchanged.

Records are content-versioned and repeat inserts are ignored by ID. This is
**application-level version preservation, not database-enforced immutability**:
privileged roles can update/delete rows. No live prediction lock or live track
record exists. Migration 0102 adds separate quarter calculation/outcome tables,
with the same public-read/service-role-write RLS conventions. Migrations 0001–0099,
including 0009, remain protected.

### Annual versus quarterly guidance

Annual records retain metric `consolidated_revenue` and their existing IDs.
Quarterly records use `quarterly_consolidated_revenue`, explicit start/end dates,
issue-date intervals, SEC filing dates, statuses, accessions, exhibits and quotes.
Selection is by **company, metric, exact period and public availability**. The
loader checks reaffirmations within that same metric/period, never against an
unrelated annual range. Both issuance and SEC availability must pass the cutoff.

The files contain ten current target quarters (Q3 FY2027 for eight January-year
companies, Q3 FY2026 for lululemon, Q4 FY2026 for Adobe), plus MongoDB's explicit
September 28 Q3 reaffirmation: eleven quarterly versions. Salesforce's October
20 statement refers to FY27 and is not invented into a Q3 reaffirmation. The
existing reviewed SEC source inventory was checked for applicable subsequent
statements. Earlier quarters and an eight-quarter outcome-history backfill are
not claimed; those belong to Session 3.

```sh
.venv/bin/python -m earnings migrate
.venv/bin/python -m earnings load-guidance ALL
.venv/bin/python -m earnings verify-guidance ALL
.venv/bin/python -m earnings quarter-growth PD --as-of 2026-11-11
.venv/bin/python -m earnings inspect QUARTER_CALCULATION_UUID
.venv/bin/python -m earnings compare BEFORE_QUARTER_UUID AFTER_QUARTER_UUID
```

`quarter-growth` is **guidance-implied YoY growth, not a forecast**:

```
implied_growth_low  = quarter_guidance_low  / prior_comparable_quarter - 1
implied_growth_high = quarter_guidance_high / prior_comparable_quarter - 1
```

For a wholly unreported quarter, no annual YTD amount is subtracted. The result
has `guidance_low/high`, not annual `remaining_low/high`. If target-quarter actuals
are already public, including a partial target-period observation, this path
blocks and directs the caller to outcome classification. The prior denominator
must match entity/concept/basis/currency and fiscal boundaries. Q4 can be derived
from annual minus explicit nine-month inputs; all parent versions are preserved.
Weekly quarter lengths must match; a 14-week Q4 is never normalized to 13 weeks.
The historical denominator is intentionally a year old and does not trigger the
135-day **current actuals** policy. The configurable/versioned 150-day guidance
age rule still applies, including its inclusive boundary. Annual freshness rules
are unchanged. `compare` refuses annual-versus-quarter attribution and separates
guidance, prior comparison, growth review, policy and eligibility changes.

### Independent comparability and selected-version outcomes

`quarter_targets[].growth_comparability` answers whether current versus prior-year
revenue is comparable. `outcome_comparability` separately answers whether guidance
matches the reported target result. Neither a passed growth review nor a growth
block decides outcome eligibility. Salesforce, Okta and SentinelOne retain their
growth blocks. Their target results are not yet public, so no result-basis review
is fabricated. Every current quarter target has an explicit pending outcome
review; annual registry outcomes also have a distinct pending review.

After the actual is filed, score an **explicit selected guidance version**:

```sh
.venv/bin/python -m earnings quarter-outcome PD --as-of YYYY-MM-DD \
  --period-end 2026-10-31 --guidance-id GUIDANCE_UUID \
  --result-issued YYYY-MM-DD --result-filed YYYY-MM-DD \
  --result-accession SEC_ACCESSION \
  --result-url https://www.sec.gov/Archives/edgar/data/.../release.htm \
  --basis-review earnings/validation/reviewed-result.json
```

The manual review JSON must identify `blocked`, `available_on`, `reason`,
`sources` (SEC URLs or objects with `url` and `filed_date`), `actual_id` and
`guidance_id`. A passing quarterly review must match the exact selected versions;
unknown, future, unsupported or blocked reviews yield `not_comparable` with
`INCOMPARABLE_BASIS`. `--not-comparable` records an explicit operator block.
Result and release filing availability, issuance interval, company, period,
concept, unit and basis are checked. Guidance issued/filed on the result date is
conservatively excluded; no intraday precedence is invented. Endpoint equality
is `within`, also for point guidance. Withdrawn selected guidance blocks. An
older valid original version can be scored explicitly without treating a later
withdrawal as a zero forecast. The CLI records whether the selected version is
original/latest, the latest pre-result status, and subsequent withdrawal history. This command is deterministic outcome
classification, not prediction-lock creation or probabilistic scoring.

### Date-source fetch observations

```sh
.venv/bin/python -m earnings.dates > data/cache/earnings/date-checks-NEW-RUN.json
```

Use a new output filename per run to preserve observations. The dates-only IR
transport rejects off-allowlist hosts and redirects. SEC date sources use the
existing fetcher with a fresh request and its cache manifest. Each observation
stores actual `checked_at`, successful `fetched_at`, source URL, hash, and status.
Failed checks retain their check time and **null fetched_at**; no earlier fetch
time is reconstructed. These are retrieval/verification observations, not a claim
that a historical estimate has become a confirmed upcoming date.

`validation/session1-date-checks.json` stores this pass's twenty observations:
eighteen successful retrievals and two HTTP 403 gaps (CrowdStrike and MongoDB IR).
Salesforce/Okta's existing dated announcements were reconfirmed. CrowdStrike and
MongoDB retain earlier confirmation provenance with the current retrieval gap
explicitly recorded. Six exact upcoming dates and annual-result windows remain
unverified/estimated. Registry `source_check` objects link the latest observations;
previous Phase 1 validation snapshots are unchanged.

### Gate evidence

`validation/session1-completion.json` records the Adobe/CrowdStrike annual
calculations with every input ID, period, accession and filing date, independently
checked statement columns, source hashes, quarterly guidance verification, and
repeat-load counts. Reproduce the two annual checks with:

```sh
.venv/bin/python -m earnings verify-real ADBE CRWD
.venv/bin/python -m pytest -q
```

The reconciliation gold now covers Adobe/CrowdStrike as well as the original
PagerDuty/GitLab examples. Adobe statements report USD millions; CrowdStrike
statements report USD thousands. Verification checks these scales and the actual
selected XBRL values independently, then recalculates the hurdle and checks the
derived remainder's parent IDs. Session 2's complete audit and Session 3's baseline
and immutable ledger remain outstanding.
