# Frozen scoring interface and publication copy

Read [CURRENT_CHECKS.md](CURRENT_CHECKS.md) before real scoring. No scoring-day command has been executed on the live ledger in the readiness task. It still contains eight predictions and zero results. Log score is **not** in the frozen schema/method; no new convention is introduced.

A review file is named for the exact prediction UUID. The following is a **non-executable field template**, not a reported outcome or completed owner review. Replace every placeholder with actual evidence; never invent amounts, dates, IDs or quotes.

```json
{
  "actual": {
    "id": "EXACT_LOADED_ACTUAL_UUID",
    "company": "COMPANY_TICKER",
    "concept": "REGISTERED_CONSOLIDATED_REVENUE_CONCEPT",
    "start": "EXACT_TARGET_START",
    "end": "EXACT_TARGET_END",
    "value": "EXACT_DECIMAL_USD_AMOUNT",
    "unit": "USD",
    "basis": "US_GAAP_consolidated_reported",
    "accession": "ACTUAL_FACT_ACCESSION",
    "filed": "ACTUAL_FACT_FILED_DATE",
    "form": "ACTUAL_FACT_FORM",
    "fiscal_year": "COPY_ACTUAL_FACT_LABEL_OR_NULL",
    "fiscal_period": "Q3",
    "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK_PADDED_COMPANY_CIK.json",
    "parents": [],
    "derivation": null
  },
  "actual_parents": [],
  "result_source": {
    "url": "EXACT_SEC_EXHIBIT_99_1_URL",
    "accession": "RESULT_8K_ACCESSION",
    "filed_date": "RESULT_8K_FILED_DATE",
    "issued_date": "RELEASE_DATELINE_DATE",
    "issuance_date_quote": "EXACT_LITERAL_DATELINE",
    "quote": "EXACT_RESULT_REVENUE_ROW_OR_PUBLICATION_PASSAGE",
    "exhibit": "99.1"
  },
  "first_result_publication_lower_bound": "EARLIEST_SUPPORTED_PUBLICATION_BOUNDARY_WITH_OFFSET",
  "evidence_available_at": "CONSERVATIVE_PUBLIC_AVAILABILITY_UPPER_BOUND_WITH_OFFSET",
  "outcome_basis_review": {
    "actual_id": "EXACT_LOADED_ACTUAL_UUID",
    "guidance_id": "EXACT_LOCKED_GUIDANCE_UUID",
    "blocked": "REPLACE_WITH_ACTUAL_BOOLEAN_AFTER_REVIEW",
    "available_on": "ACTUAL_REVIEW_DATE",
    "reviewed_at": "ACTUAL_REVIEW_TIMESTAMP_WITH_OFFSET",
    "verifier": "ACTUAL_OWNER_REVIEWER",
    "reason": "SOURCE_BACKED_SCOPE_PERIOD_UNIT_BASIS_DECISION",
    "sources": [{"url": "EXACT_SEC_SOURCE_URL", "filed_date": "SOURCE_FILED_DATE"}]
  }
}
```

Preserve supplementary table headers, column identification, scale, source hashes and owner attestation alongside each review. Matching a quote does not prove its semantics or units; the frozen verifier checks literal presence and exact companyfacts versions, while the owner must verify the Item2.02→Exhibit99.1 relationship, actual table interpretation and comparability. Q3 requires a direct three-month actual. If the release is rounded and the exact companyfacts amount is unavailable or classification-sensitive, block rather than manufacture precision.

For all eight prediction UUIDs and exact guidance IDs, consult `publication/predictions.json` or the copied SQLite archive; do not select current guidance afresh. Future result/score correction records stay append-only; latest versions in a publication copy are displayed with a version count.

## Read-only copy and publication workflow

Follow [SCORING_DAY.md](SCORING_DAY.md) for the complete owner checklist, timing estimates, exact commands and failure handling. After separate real-scoring approval, export using `python -m earnings.publication.export --output REVIEW_PUBLICATION_DIR/predictions.json --copy-dir PRIVATE_ARCHIVE_DIR`; review the new archive/JSON, copy the unchanged reviewed `backtest.json` alongside it, then generate the seed with `python -m earnings.publication.snapshot_sql --input-dir REVIEW_PUBLICATION_DIR --output NEW_REVIEWED_SEED.sql`. This explicit input prevents accidentally regenerating an older pending copy.

The export opens a REPEATABLE READ, READ ONLY transaction under the read role; the private SQLite archive preserves its content hash and source evidence. Public JSON excludes raw owner attestations and connection details. Evidence digests are reproducible publication-time hashes, not independent lock-time notarization. Pending means no copied reviewed score, not proof of no external publication.

The website now reads **standalone snapshot tables** using `CROSSCHECK_PUBLISHED_DATABASE_URL` and the SELECT-only `dealtrace_web` role, not JSON files directly. It has no live-ledger/DATABASE_URL fallback. The old `CROSSCHECK_PUBLISHED_SNAPSHOT` file-path description is obsolete. Owner setup and SQL grants/RLS are in `publication/README.md`; manually review/apply the new seed to the publication database. This is not permission to score or publish. Browser visual compatibility remains unverified.

## Scratch rehearsal (never live scoring)

```sh
.venv/bin/python -m earnings.scoring_readiness --copy /absolute/path/exported-copy.sqlite3 --output /absolute/path/new-rehearsal.json
```

Reads observations from the separately exported copy. Three historical cases are deliberately selected for known below/within/above coverage, and both methods are reconstructed with public-date filtering under the unchanged historical horizon. This is a mechanics test, **not** held-out performance, a live forecast or calibration evidence. Historical as-of values are selection coordinates in fixture payloads; actual scratch creation/scoring timestamps are database-generated now.

The frozen `verify_sources`, `evaluate`, `save` and `run` execute on TEMP actual/result tables and a TEMP prediction **view** over explicitly marked retrospective scratch inputs. No prediction table/record is created. A scratch-only SQL adapter and `pg_temp` search path prevent scorer SQL from addressing live tables. The result-trigger body is copied unchanged into `pg_temp`, never replacing public functions. Repetition inserts no duplicate scratch scores; an incorrect Brier is rejected. Everything rolls back/disappears when the session closes.

Tests for this pass run with `DATABASE_URL=''` to prevent the repository's existing DB fixtures from creating even rollback-only rows in the live ledger. New unit tests use committed public/history data, not private cache dependencies. The scratch PostgreSQL rehearsal is executed separately and is the only write-backed scoring verification.

## All-lock synthetic PostgreSQL publication rehearsal

`earnings.scoring_pipeline_rehearsal` tests the eight copied real locks without creating predictions. It requires an explicit `CROSSCHECK_REHEARSAL_DATABASE_URL` pointing to a database named `crosscheck_scoring_rehearsal_*` on the private localhost port65439 cluster whose data directory starts `/tmp/crosscheck-snapshot-pg-`. It never uses `DATABASE_URL`. Verify that private cluster first, create the scratch database and then use:

```sh
.venv/bin/python -m earnings.scoring_pipeline_rehearsal --copy PRIVATE_SOURCE_ARCHIVE.sqlite3 --output data/cache/earnings/scoring-pipeline-rehearsal/NEW_UNIQUE_RUN
```

The source archive must contain zero scores for this bounded first-scoring rehearsal. Its predictions become a TEMP view with their original IDs/timestamps/snapshots, not new lock rows. Fabricated source responses are in memory only; source/review fixtures are labelled synthetic and never owner-verified. Scoring uses real PostgreSQL clocks. The output directory is constrained to the ignored private rehearsal cache, and its generated synthetic seed has a private-database guard. No fabricated JSON/seed may be promoted into the normal publication directory or a real publication database.

The November22 run scored all8, repeated without duplicates, blocked future evidence, regenerated both copy tables/seed, and verified SELECT-only access. This validates mechanics, not real SEC availability, source semantics, owner review or future results. See `reports/scoring_pipeline_rehearsal_2026-11-22.md`.
