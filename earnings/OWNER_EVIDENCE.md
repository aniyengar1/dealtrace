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

Before future locks, original PDF/review integrity is checked locally without re-downloading the historical announcement. The separate `integrity_check.integrity_checked_at` records hashing time; original retrieval, source `checked_at`, supplier and review provenance remain unchanged. A hash proves integrity, not authenticity or a current schedule/publication check.

Owner-approved `current-state-checks-v2` / migration0106 supersedes the old ten-minute PDF retrieval and two-minute publication rules. Durable evidence remains valid, while the current schedule/publication checks and independent SEC check must each be <=ten minutes old at DB insertion. An owner-browser attestation can cover inaccessible official sources; no fabricated timestamps or inference from SEC absence. Missing, stale, changed or contradictory coverage blocks. Follow [CURRENT_CHECKS.md](CURRENT_CHECKS.md). No actual owner attestations or CRWD/MDB files have been supplied in this pass.
