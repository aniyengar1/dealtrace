# December 1–3 scoring-day runbook

**Procedure only. Real scoring and publication require separate owner authorization.** The November23UTC READ ONLY copy contains **12 locks for OKTA/CRM/IOT/S/GTLB/CRWD**, two methods per company, and zero scores. MDB is not locked in this copy; include it only if actual authorized locks later exist. Never recreate a prediction during scoring, choose new guidance, or alter its timestamp.

Current schedule: Dec1 OKTA/GTLB/CRWD; Dec2 CRM; Dec3 IOT/S, all after close. The calendar is a planning aid, not evidence that results have or have not appeared. MDB has a Dec1 planning date but no prediction in this copy. For discovery URLs and ordinary four-business-day 8-K planning windows, use CURRENT_CHECKS.md. Actual companyfacts availability can lag the press release and 8-K; there is no guaranteed same-evening score.

## Manual steps and time budget

Human times below are **estimates, not measured review times**. Automated timings measured in the synthetic rehearsal are separate. Stop for ambiguity rather than working to a time target.

| Step | Owner action / acceptance check | Estimated active time |
|---|---|---|
| 1 | Confirm approved branch/checkpoint and READ ONLY list of actual prediction UUIDs, locked guidance IDs and immutable target periods; identify which companies reported today. | 3–5 min once |
| 2 | Find the new official results and SEC Item2.02 8-K; open its **actual linked Exhibit99.1**. Save URL, accession, dateline, filing date/hash and any earlier preliminary disclosure. A call time or SEC acceptance time is not the first-publication time. | 3–8 min/company; passive filing wait unknown |
| 3 | Read the **consolidated reported revenue, three months ended October31,2026** table column, headers, USD scale, exact amount and basis. Reject ARR, segment-only, adjusted, organic, constant-currency and YTD substitutions. No Q3 YTD subtraction. | 5–10 min/company |
| 4 | Refresh actuals through the existing SEC fetcher; inspect the exact loaded actual UUID/accession. Reconcile release amount to companyfacts and any amendment. Rounded release amounts must not be turned into invented exact facts. | 2–5 min/company; XBRL publication wait unknown |
| 5 | Owner records actual-versus-locked-guidance scope/period/unit comparability and sources. Keep growth-denominator concerns separate. For MDB, resolve Firebolt legal close/consolidation timing if it later becomes locked. | 5–15 min/company; longer/unresolved cases block |
| 6 | Prepare one reviewed outcome JSON per prediction UUID using SCORING.md. Both methods share the actual but each file binds its exact locked guidance/prediction. Preserve your real name, review time and decision. Never copy the rehearsal's made-up sources, dates or amounts. | 5–10 min/company pair |
| 7 | Run the scorer only after both source and actual availability intervals have closed; inspect every returned entry. Other companies awaiting results normally show MISSING_REVIEWED_OUTCOME. An exit code0 alone is not approval: unexpected blocked entries for the company being scored require investigation. | 2–4 min/batch plus source/network time |
| 8 | READ ONLY inspect the inserted score IDs/outcomes/Brier and correction links. Verify exactly two method scores per newly scored company, no duplicates, all original locks unchanged. | 3–5 min/batch |
| 9 | Export a new READ ONLY SQLite archive and public JSON to an isolated review directory. Review the resulting actuals, scores, still-pending companies, counts and hashes. | 3–5 min/batch |
| 10 | Copy the unchanged reviewed BACKTEST summary into that directory; generate a seed from **that explicit directory**. Confirm SQL writes only the two publication-copy tables. Owner applies it using the configured administrative connection/SQL editor; web role stays SELECT-only. | 3–5 min/batch |
| 11 | Verify published rows using the dedicated dealtrace_web connection; inspect `/crosscheck/predictions` in your own browser, including pending/scored counts, actuals, Brier and evidence. Keep the export/seed/apply time and any failures. | 3–5 min/batch |

Allow roughly **20–50 active minutes per straightforward company pair**, plus15–30 minutes of shared batch work and unbounded passive SEC/XBRL waiting. These estimates are not a promise or a cap on comparability research. No real human source review was timed or completed by the synthetic rehearsal.

## Commands — real data only, after separate authorization

Choose new directories/filenames for every execution. Replace placeholders explicitly; no commands below create predictions. No live command is run by this document.

```sh
# Example first batch; use only companies that actually reported and are locked.
.venv/bin/python -m earnings ingest OKTA --refresh
.venv/bin/python -m earnings inspect EXACT_LOADED_ACTUAL_UUID

# Prepare and personally review UUID-v1.json files in REVIEW_DIR first.
.venv/bin/python -m earnings.score_live --review-dir REVIEW_DIR --output NEW_UNIQUE_SCORING_EXECUTION.json

# Inspect execution JSON and reviewed ledger results before publication.
# REVIEW_PUBLICATION_DIR must be a new directory; the archive remains private.
.venv/bin/python -m earnings.publication.export --copy-dir PRIVATE_ARCHIVE_DIR --output REVIEW_PUBLICATION_DIR/predictions.json
cp earnings/publication/backtest.json REVIEW_PUBLICATION_DIR/backtest.json
.venv/bin/python -m earnings.publication.snapshot_sql --input-dir REVIEW_PUBLICATION_DIR --output NEW_REVIEWED_SEED.sql
```

Review/apply the new seed to the intended **publication database**, after its one-time `earnings/sql/published_snapshots.sql` setup. Never change the site's connection to the live ledger. The site reads `crosscheck_prediction_snapshots` and `crosscheck_backtest_snapshots` via `CROSSCHECK_PUBLISHED_DATABASE_URL`, not JSON files directly. No inferred copying or automatic deployment occurs. Partial daily publication is valid: companies not yet reviewed remain pending.

## Availability and corrections

- Guidance classification is below `< low`, within inclusive endpoints, above `> high`; score against the **locked** version only.
- Frozen Brier is unscaled `sum((p_k - indicator_k)^2)`,0 best/2 worst. Log score is not implemented in the frozen method; do not introduce clipping or a zero-probability convention.
- `verify_sources` requires exact matching companyfacts, literal release evidence and a dated release. Owner review must establish table semantics, correct Item2.02→99.1 linkage, units, first-publication evidence and comparability. Literal matching does not establish those semantic facts or authenticate the reviewer.
- Day-precision SEC evidence is conservatively available only after the next New York midnight for **both** actual and result filing. Missing XBRL blocks scoring; a press release alone is insufficient. This can delay scoring beyond Dec1–3.
- Re-running the same evidence creates no duplicate score. Corrections require a new reviewed actual/source version and a new UUID-v2.json file; records append with a supersedes link. Never update/delete an old score or lock. Publication shows the latest copied version and its version count.
- A blocked comparison is not a synthetic miss or zero actual. Preserve the evidence and unresolved question. No missing amount becomes zero.

## What the November22 synthetic rehearsal establishes

It copied all eight real locks unchanged into a TEMP **view** over private copied inputs, not a prediction table or a new lock. Fabricated actuals/source responses were supplied in memory to the unchanged source verifier, scorer and frozen SQL Brier trigger. Synthetic release dates were deliberately after the original locks and before the actual current date so the time guard could be exercised without changing a DB clock. These are not claims about actual publication or human verification. All score timestamps came from actual PostgreSQL clocks.

All eight scored, repeat scoring inserted zero duplicates, future evidence blocked, export/archive checks passed, and the two published copy tables/seed were regenerated and read under dealtrace_web. Seed reapplication was idempotent; INSERT/UPDATE/DELETE/TRUNCATE were denied to the publication role. All artifacts remain clearly marked synthetic in the ignored rehearsal cache. No synthetic result or seed was copied into the production publication files, live tables or website.

## November 23 twelve-lock rehearsal update

A fresh READ ONLY live export confirmed all **12 predictions** (OKTA, CRM, IOT, S, GTLB, CRWD × two methods) and **zero live scores**. The complete isolated scratch run scored **12/12**, repeat scoring inserted **zero duplicates**, and regenerated/exported a scored public-shaped snapshot and valid guarded synthetic seed. The seed was applied twice only to private publication-copy tables and read successfully under `dealtrace_web`; reader writes remained denied. Live rows and hash were identical before/after. See `earnings/reports/scoring_pipeline_rehearsal_twelve_2026-11-23.md`.

**Clock qualification:** actual execution was November 23. The day-precision fixture for November 22 locks needs a November 23 release, available only November 24 at midnight Eastern. The real-clock attempt correctly blocked. To rehearse all 12 immediately, a forward-only **test clock of November 24, 05:00:01 UTC** was explicitly confined to the scratch scoring application and copied TEMP result-trigger timestamp. Production code/guards/database clocks and original lock timestamps stayed unchanged. This test is not a real score or backdated execution. Real scoring must still wait for actual source availability; the test-clock option exists only in the isolated rehearsal CLI and is not a scoring-day command.

Automatic local timings: scoring plus duplicate repeat **0.452s**; archive/export/seed/application/read **0.153s**; scratch migrations **0.261s**. These use in-memory sources and exclude real SEC waits and human verification. No scoring-day manual step or estimated human-time budget changed. Production publication files were not regenerated or applied.
