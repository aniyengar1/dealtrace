# Owner-assisted pre-lock checklist (current-state-checks-v2)

This is a manual procedure, not a scheduled job. **Current state: eight immutable predictions were locked November17 for OKTA/CRM/IOT/S, two methods each.** No additional locks or live scores are authorized by a read-only readiness task. Earlier preparation notes below retain their historical context. The actual PostgreSQL clock controls creation and eligibility; test clocks cannot be passed to the production command.

Durable evidence retains its original source URL, PDF/body, SHA-256, supplier, true retrieval/ingestion/verification times and attribution. File hashing checks integrity only. The ten-minute rule now applies to **current schedule and publication checks**, including each independent SEC/IR component, at insertion; it does not expire a historical announcement. This supersedes the former two-minute publication and ten-minute PDF retrieval rules. Migration0106 enforces the new policy alongside existing immutable snapshots, probability guards and duplicate protection. Old tags are preserved but must not be used to bypass the current schema guard.

## Entry windows and planned owner session

Provided the reviewed December1 results date remains unchanged: **November13,2026 21:00 America/Los_Angeles = November14 05:00UTC**. Lock strictly before **December1 00:00 America/New_York = December1 05:00UTC**. “After market close” is not an exact publication time. Do not substitute the call time or16:00. Before the opening, the CLI skips; at the deadline it rejects. The old14-day entry rule is superseded by **17 release-local calendar days**, policy `live-entry-17-calendar-days-v1`, enforced in Python and migration0107. These are eligibility boundaries, not automatic jobs or authorization to lock earlier. **The planned owner lock session remains Monday, November16 after21:00 Pacific (November17 after05:00UTC).** No live predictions are authorized by this preparation.

Target: Q3FY2027, **August1–October31,2026**. Current stored range: **$813–817million**, guidance `7790a72a-98d9-57b3-9287-bf22cba52401` (August26 issuance/SEC availability, accession0001660134-26-000068). Seven eligible outcomes: below0 / within0 / above7. Empirical probabilities0/0/1; Laplace0.1/0.1/0.8. Both methods use the same selected inputs and cutoff. Refreshing input data may reveal a legitimate new block; these figures are not frozen future source checks.

## Owner checklist when official automated access fails

1. Before the short current-check window, update SEC facts and load only reviewed manual guidance. Review new input/evidence versions; extracted candidates remain quarantined. No Vertex or other model calls are involved.
2. Personally open the **exact** official announcement URL, news inventory and quarterly-results inventory below in your own browser. Check results **publication**, not a webcast/call. Cover every page/filter/year needed from target start through the actual check date, including preliminary results and schedule changes. Open relevant linked entries. A loading shell, inaccessible page, incomplete pagination or uncertainty is not a negative result; stop and record a gap.
3. Record each exact URL (and final URL if redirected), actual page-check timestamp with numeric UTC offset and IANA timezone, and second/minute precision. Do not copy the announcement's historical retrieval time into these fields, or use file/hash/entry time as page-check time. Record the actual automation failure URL/reason as owner-reported, without claiming an independently observed HTTP status unless supported.
4. Confirm the unchanged December1 after-close results schedule in America/New_York against durable evidence. If a date, timezone or publication interpretation changes, **stop**, preserve the observation and append/review a new durable evidence version. Do not edit prior evidence or label unknown timing verified.
5. Report target or preliminary results already public, contradictions, missing coverage or unresolved timing as a block. SEC absence alone is insufficient. Only attest `not_observed` if you actually completed all coverage. Identify yourself as the observer; browser observations are `user_verified`, not independently HTTP-verified by Codex.
6. Fill a copy of [owner_current_check_template.json](owner_current_check_template.json) outside the intake record directory. It intentionally contains null times and false/unknown observations. It is **not** an attestation. All observations must be supplied by you. The one schedule passage may cover multiple roles if that accurately describes your inspection; no invented duplicate evidence is needed.
7. Intake the completed form. It preserves original JSON bytes/hash and actual ingestion time; it never locks a prediction. Confirm assessment `usable`, correct target and original announcement ID. Blocked observations are also preserved; a latest blocked intake is not replaced by an older favorable one. Recheck pages honestly if the earliest page time will be older than ten minutes by insertion.
8. During the planned November16 after21:00Pacific session, manually invoke both-method locking only under separate live-lock authorization. Earlier eligibility alone is not permission to execute. The command performs its **own independent fresh SEC submissions check**, then revalidates owner freshness after the fetch. Failure or possible SEC results blocks. It records both methods atomically, with actual DB creation times and self-contained evidence. No `--as-of` option exists. Keep the execution output even for zero locks.

Official pages for Okta (check the entire relevant content):

- Announcement: https://investor.okta.com/news-and-events/news-releases/news-details/2026/Okta-to-Announce-Third-Quarter-Fiscal-Year-2027-Financial-Results-on-December-1-2026/default.aspx
- News and pagination: https://investor.okta.com/news-and-events/news-releases/default.aspx
- Quarterly results: https://investor.okta.com/financials/quarterly-results/default.aspx
- Independent SEC check, fetched by code: https://data.sec.gov/submissions/CIK0001660134.json

Run from the earnings worktree with the isolated `.venv`. Verify the checkpoint/schema first. Migrations0106 and0107 must be applied. The baseline/history selection remains unchanged; early locks cannot select guidance unavailable at actual locking. Dependencies remain pinned in `earnings/lock_ready/two_method_requirements.lock`; no shared environment changes.

```sh
# Before the short evidence window; review updated data before proceeding:
.venv/bin/python -m db.migrate
.venv/bin/python -m earnings ingest ALL --refresh
.venv/bin/python -m earnings load-guidance ALL

# After your actual checks; does not lock anything:
.venv/bin/python -m earnings.current_checks /absolute/path/completed-owner-check.json --directory data/cache/earnings/current-checks

# FUTURE MANUAL COMMAND ONLY: planned Nov16 AFTER21:00 Pacific, with fresh usable checks:
.venv/bin/python -m earnings.predict --lock --methods both --owner-check-dir data/cache/earnings/current-checks
```

The default unique execution filename is printed and saved under `data/cache/earnings/lock-runs/`. With this directory, companies without an owner check use automated checks; an incomplete/stale owner record blocks instead of silently falling back. An explicit output filename must be new. Do not rerun a partial method pair with new inputs; the CLI blocks it for review. Duplicate protection includes method version.

## Limits and remaining real blockers

Owner-browser checks were supplied and preserved for the four completed locks; those expired observations must never be reused for another lock. Fresh source checks are required for any separately authorized future lock; this document, the old announcement, and synthetic rehearsals do not establish freshness. Historical evidence must still pass local integrity checks. CRWD/MDB owner PDFs were received and verified November20; durable evidence is preserved in announcements/CRWD.json and announcements/MDB.json. They remain unlocked and require fresh current-state checks. Missing dates for other companies remain unverified.

Human observations can be incomplete or mistaken; browser caching, wrong clocks, overlooked preliminary publication and incomplete inventories remain risks. Official sources plus SEC are not complete internet surveillance; a check-to-insert race remains. An attestation or SHA does not establish authenticity by itself. The DB protects ordinary application writes and immutable locked snapshots, not a DBA who changes enforcement or a dishonest operator. No eligibility, probability or outcome-quality guarantee follows from passing these checks.

## Uniform17-day entry table

| Company/current verified release | Eligibility opens Eastern | Eligibility opens Pacific | Strict deadline Eastern |
|---|---|---|---|
| OKTA / December1 | November14,00:00 | November13,21:00 | December1,00:00 |
| CRM / December2 | November15,00:00 | November14,21:00 | December2,00:00 |
| IOT and S / December3 | November16,00:00 | November15,21:00 | December3,00:00 |

All four are within the timing window at the planned Monday session, **conditional on all evidence and other gates**. CRWD/MDB’s December1 dates are now supported by the November20 owner-PDF intake; they share the first opening but remain unlocked. GitLab’s November17 official announcement is also verified; see reports/lock_prep_2026-11-20.md. Other unsupported dates remain unverified. Prepare company-specific current checks using each actual official announcement, news and results URL; do not copy Okta observations to another company. Existing owner-attribution, coverage, timestamp, freshness and SEC requirements are unchanged.

The extractor is shelved. Owner extraction review is **deferred, not performed**; do not resume inference, tuning or extraction review. Manual reviewed guidance remains the only target input. Preserve the original random packet/fresh groups and all reservations.

## December 1–3 scoring desk card — reviewed November 20, 2026

**Preparation only: do not run scoring without results and separate owner approval.** The READ ONLY ledger check at 2026-11-21T02:03:36Z found eight predictions for OKTA/CRM/IOT/S, zero scores. GTLB/CRWD/MDB are **not locked**; include them only if a later READ ONLY ledger check confirms actual prospective records. Never create a prediction during scoring.

All targets below are **Q3 FY2027, August1–October31,2026, consolidated reported USD revenue**. All currently verified releases are after market close. Plan to look for the Item2.02 8-K the same evening/next business day; that is a workflow expectation, not a confirmed future filing time. Most 8-K disclosures are due within four business days ([SEC guidance](https://www.sec.gov/files/readan8k.pdf)); for these dates the ordinary outer planning dates are December7/8/9 respectively. A later SEC filing is not the first-publication timestamp, and no filing is not proof of no public result.

| Company | Results date | Check for 8-K / ordinary four-business-day planning date | Exact SEC discovery source |
|---|---|---|---|
| Okta (OKTA), locked | Dec1 | Dec1 evening–Dec2 / Dec7 | [CIK0001660134 submissions](https://data.sec.gov/submissions/CIK0001660134.json) |
| Salesforce (CRM), locked | Dec2 | Dec2 evening–Dec3 / Dec8 | [CIK0001108524 submissions](https://data.sec.gov/submissions/CIK0001108524.json) |
| Samsara (IOT), locked | Dec3 | Dec3 evening–Dec4 / Dec9 | [CIK0001642896 submissions](https://data.sec.gov/submissions/CIK0001642896.json) |
| SentinelOne (S), locked | Dec3 | Dec3 evening–Dec4 / Dec9 | [CIK0001583708 submissions](https://data.sec.gov/submissions/CIK0001583708.json) |
| GitLab (GTLB), conditional | Dec1 | Dec1 evening–Dec2 / Dec7 | [CIK0001653482 submissions](https://data.sec.gov/submissions/CIK0001653482.json) |
| CrowdStrike (CRWD), conditional | Dec1 | Dec1 evening–Dec2 / Dec7 | [CIK0001535527 submissions](https://data.sec.gov/submissions/CIK0001535527.json) |
| MongoDB (MDB), conditional | Dec1 | Dec1 evening–Dec2 / Dec7 | [CIK0001441816 submissions](https://data.sec.gov/submissions/CIK0001441816.json) |

1. **Find the actual:** use the existing SEC fetcher for the new Item2.02 8-K and follow its actual **Exhibit99.1 earnings-release link**. The future accessions/exhibit URLs do not exist in this review; do not guess them or use the old guidance exhibit. Record accession, filed date, exact exhibit URL/hash and dateline. Read the consolidated income statement’s **three months ended October31,2026 revenue column**, with headers, USD scale and literal row. No ARR, subscriptions/segment-only revenue, YTD, adjusted or constant-currency substitutes; no YTD subtraction.
2. **Owner verifies:** issuer/quarter/units, exact locked guidance ID and both prediction UUIDs; amount versus the release and exact matching companyfacts version; earliest public actual/preliminary disclosure (not call time); acquisition/recast/basis compatibility. Keep Salesforce/Okta/SentinelOne growth-only concerns separate from guidance-to-result scoring. Review MongoDB/Firebolt effective accounting date if MDB becomes locked. Any unresolved discrepancy blocks. Preserve actual owner identity/time and evidence; no pre-completed attestation.
3. **Prepare review files:** follow [SCORING.md](SCORING.md), one `<prediction-UUID>-v1.json` per method. Use existing actual IDs, exact locked guidance, and genuine availability dates. The frozen verifier requires matching companyfacts; a release alone may not yet score. Day-precision filing evidence becomes usable only after the next New York midnight. Wait for missing facts; never backdate. Corrections append new reviews/scores, never overwrite.
4. **Future commands, only after approval:** refresh the actuals for the companies being scored, then score reviewed UUID files. The same command handles both methods for every row; there is no invented company-specific score flag. Include GTLB/CRWD/MDB in ingestion only if actually locked.

```sh
.venv/bin/python -m earnings ingest OKTA CRM IOT S --refresh
.venv/bin/python -m earnings inspect ACTUAL_UUID
.venv/bin/python -m earnings.score_live --review-dir /absolute/path/reviewed-outcomes --output /absolute/path/new-unique-scoring-execution.json
```

Inclusive endpoints; unscaled multiclass Brier0..2, lower better. Frozen log score is absent; do not invent clipping or change zero-probability buckets. Publish only after reviewing the score execution and separately refreshing the publication copy. Detailed review fields and safeguards follow below.

## Scoring-day procedure — after December1–3 results (not executed in this readiness pass)

The November17 owner-authorized session created eight live records: empirical and Laplace pairs for OKTA, CRM, IOT and S. They remain immutable. Their target dates are December1 (OKTA), December2 (CRM), December3 (IOT/S). No new prediction or score is authorized by a readiness rehearsal. **Never rerun a lock to change an existing target or probability.**

1. Locate the company's **8-K Item2.02 and its linked earnings-release Exhibit99.1** on SEC EDGAR. Record the primary8-K accession, filing date, exact exhibit URL and the release's literal dateline. An IR release can establish earlier public publication timing, but the scoring evidence must include the SEC release. A call, slide-deck projection, analyst estimate or later filing time is not the first publication time. Include earlier preliminary results when establishing the earliest public-results boundary.
2. Read the **reported consolidated revenue** row in the income statement, with table headers, exact fiscal dates, currency, units and quarter column. Do not use YTD, ARR, segment revenue, organic/constant-currency figures or an adjusted metric. All four locked targets are Q3, so **no YTD subtraction** applies. Multiply explicit scale by Decimal; preserve the quoted table row and headers. Reconcile to the exact matching SEC companyfacts version and accession, preserving amendments/restatements. Do not force a result where rounding, scope or fiscal-period evidence is ambiguous.
3. Refresh companyfacts through the existing fetcher. Frozen `verify_sources` requires an exact matching companyfacts period/value/unit/accession/filed version; a press release alone is **not sufficient** if that fact is not available yet. Day-precision filing/issuance intervals close at the next New York midnight. Wait for genuine availability; do not backdate evidence or bypass this gate to score on release night. Q4 derivation, if used in future, requires compatible annual/nine-month parents and both versions' availability.
4. The owner reviews each exact locked guidance ID and result actual ID for **guidance-to-result comparability**, separate from YoY-growth comparability. Inspect acquisition/divestiture/recast disclosures and basis changes. Record actual reviewer identity, actual review time, dated SEC sources, and a pass or specific unresolved/block reason. Owner review is not complete until actually supplied; prior agent-curated examples do not substitute for it. No silent scope normalization.
5. Prepare outcome review JSON files under a dedicated directory, named `<prediction UUID>-v1.json`. Both method records for a company share guidance/actual evidence but must each have their own UUID-prefixed file. Use [scoring review format](SCORING.md). `actual.id` must reproduce the complete immutable Actual payload; retrieve an existing loaded record with `python -m earnings inspect ACTUAL_UUID`, rather than inventing an ID. Preserve original review/result files; corrections are new files and append-only score versions, never overwrites.
6. Check that `first_result_publication_lower_bound` is the **earliest** observed publication boundary. With day-only evidence use00:00 America/New_York on that date; never infer precision from the call or SEC filing. `evidence_available_at` must be no earlier than the closed intervals of the actual and result-source filings. **Do not supply `actual_filing_accepted_at`**: exact acceptance verification is not implemented and the frozen verifier rejects that assertion.
7. Only after genuine results availability and explicit owner authorization to score, run the future commands below. The scorer uses the real database clock, exact locked guidance and probabilities. Missing, non-comparable, unavailable or non-prospective evidence blocks; zero is never substituted. Repeat execution is idempotent. Reviewed corrections preserve the original score via `supersedes_id`.

```sh
# FUTURE SCORING ONLY — requires actual results and reviewed outcome files.
.venv/bin/python -m earnings ingest OKTA CRM IOT S --refresh
.venv/bin/python -m earnings.score_live --review-dir /absolute/path/reviewed-outcomes --output /absolute/path/new-unique-scoring-execution.json

# After reviewing the scoring execution, refresh the separate publication copy:
.venv/bin/python -m earnings.publication.export
```

The score command appends to the live results table and must **not** be run during a read-only readiness task. Publication export is READ ONLY against the source; it archives a separate SQLite copy and refreshes a sanitized JSON file. `/crosscheck/predictions` reads that JSON only, never `DATABASE_URL` or a ledger connection. Pending means no reviewed score in the copy, not proof no results have been published. Copy freshness is displayed.

**Frozen score rules:** below `< low`; within `low <= actual <= high`; above `> high`; point guidance equality is within. Unscaled multiclass Brier is `sum((p_k - indicator_k)^2)`, range0..2. **Log score is not defined/implemented in the frozen checkpoint**, including zero-probability handling. No clipping, epsilon or new scoring convention has been added. Under conventional mathematics, `log(0)=-infinity` and negative-log loss would be `+infinity`; those are not existing stored metrics. OKTA/IOT empirical below/within buckets are0. A future log metric requires an explicitly approved convention and version; it cannot rewrite probabilities or pretend the rule was frozen earlier.
