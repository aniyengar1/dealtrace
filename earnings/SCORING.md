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

## Read-only copy workflow

```sh
.venv/bin/python -m earnings.publication.export
```

This opens a REPEATABLE READ, READ ONLY transaction with the public read role, copies predictions/results/history into a new local SQLite archive under `data/cache/earnings/publication/`, verifies its content hash, and publishes `earnings/publication/predictions.json`. The archive retains private owner evidence locally and is ignored; the public JSON excludes owner names, raw attestations and source connection details. No locks, outcomes or source rows are changed. The web route imports only a file reader and pure format/validation helpers. It has no live DB fallback.

Evidence SHA256 is computed from each immutable `announcement`, `publication_check`, and full `snapshot` using the existing `earnings.models.digest` canonical format. It is a reproducible digest calculated for publication, **not an independently notarized lock-time hash**. The ledger-copy hash covers the complete copied prediction/result rows. File-copy timestamps and hash definitions are displayed. Public pending status means no copied reviewed score, not a statement about external publication status.

Launch the existing app from `apps/web` with `npm run dev`; open `/crosscheck/predictions`. Optional `CROSSCHECK_PUBLISHED_SNAPSHOT` points to a different reviewed JSON copy. No database setting is required for this route. The black/silver styling is confined to a CSS module; shared navigation, global CSS, deal pages, Tailwind/PostCSS and dependencies are unchanged. No browser automation or screenshot was used; visual compatibility still requires owner review before merging.

## Scratch rehearsal (never live scoring)

```sh
.venv/bin/python -m earnings.scoring_readiness --copy /absolute/path/exported-copy.sqlite3 --output /absolute/path/new-rehearsal.json
```

Reads observations from the separately exported copy. Three historical cases are deliberately selected for known below/within/above coverage, and both methods are reconstructed with public-date filtering under the unchanged historical horizon. This is a mechanics test, **not** held-out performance, a live forecast or calibration evidence. Historical as-of values are selection coordinates in fixture payloads; actual scratch creation/scoring timestamps are database-generated now.

The frozen `verify_sources`, `evaluate`, `save` and `run` execute on TEMP actual/result tables and a TEMP prediction **view** over explicitly marked retrospective scratch inputs. No prediction table/record is created. A scratch-only SQL adapter and `pg_temp` search path prevent scorer SQL from addressing live tables. The result-trigger body is copied unchanged into `pg_temp`, never replacing public functions. Repetition inserts no duplicate scratch scores; an incorrect Brier is rejected. Everything rolls back/disappears when the session closes.

Tests for this pass run with `DATABASE_URL=''` to prevent the repository's existing DB fixtures from creating even rollback-only rows in the live ledger. New unit tests use committed public/history data, not private cache dependencies. The scratch PostgreSQL rehearsal is executed separately and is the only write-backed scoring verification.
