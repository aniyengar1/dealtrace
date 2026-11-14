# Owner announcement intake (CRWD and MDB pending)

No files or dates have been promoted. Supply original official announcement PDF, original URL and timezone-aware retrieval time. Expected December1 after-close timing is a lead until the file supports it. The path is independent of the blocked announcement HTTP request. No credentials or `.env` are read.

Setup in the isolated earnings `.venv`: `python -m pip install -r earnings/owner_evidence_requirements.txt` (pypdf7.0.1). PDF contents are untrusted; embedded instructions are not executed. No OCR is performed. Scanned/encrypted/unparseable files remain preserved with explicit gaps.

Create a metadata JSON containing exactly `company`, `supplied_by`, `source_url`, `owner_retrieved_at`; use the actual owner-reported retrieval timestamp, never estimated or backdated. Example fields are not confirmation records.

```sh
.venv/bin/python -m earnings.owner_evidence ingest --pdf /absolute/path/owner-announcement.pdf --metadata /absolute/path/metadata.json
```

This copies the original bytes content-addressed by SHA256 and creates a uniquely timestamped intake under `data/cache/earnings/owner-announcements/`. It never automatically adds a registry date. Save the returned intake UUID. Inspect the entire PDF and extracted canonical text; distinguish company, fiscal quarter/year, announcement dateline, results publication and separate call information. Record any contradiction.

Prepare a review JSON with exactly `announcement_issued_date`, `release_date`, `release_time`, `time_precision`, `timezone`, `timezone_provenance`, `quotes`, `reviewed_by`, `review_note`. Quotes must establish `company`, `fiscal_period`, `announcement_date`, `release_date`, `results_publication`, `release_time`. The same passage may support multiple fields. Dates and market-session wording must match; absent evidence is a gap. `reviewed_by` names the actual document reviewer; supplier provenance remains separate. Exact quote matching is not proof of authenticity or semantic correctness.

```sh
.venv/bin/python -m earnings.owner_evidence review --intake-id INTAKE_UUID --review /absolute/path/review.json
# Only after reading the full supplied PDF and resolving the reported gaps:
.venv/bin/python -m earnings.owner_evidence review --intake-id INTAKE_UUID --review /absolute/path/review.json --append
```

The optional append creates a new user_verified evidence version; it refuses unresolved gaps and preserves all previous versions/403 records. It does not lock predictions. Original files and raw intake/review records stay ignored; approved public evidence summaries may be committed after review. SHA256 proves retained bytes, not who published the document.

Before future locks, `refresh_announcement` recognizes this route and rechecks local file/review integrity without retrying the blocked announcement download. The current integrity-check timestamp is separate; source checked_at remains the owner-reported retrieval time and must satisfy the existing ten-minute rule. A stale owner PDF does not become fresh by hashing it. Supply a new actual owner retrieval/review version at lock time or approve a separate freshness-policy change. The separate already-public check still requires fresh SEC and observable official news inventory access. If that inventory is403 or incomplete, lock stays blocked. No fallback to an assumed absence of results.
