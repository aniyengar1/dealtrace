# Owner-assisted pre-lock checklist (current-state-checks-v2)

This is a manual procedure, not a scheduled job or a completed owner attestation. No live predictions have been created. The actual PostgreSQL clock controls creation and eligibility; test clocks cannot be passed to the production command.

Durable evidence retains its original source URL, PDF/body, SHA-256, supplier, true retrieval/ingestion/verification times and attribution. File hashing checks integrity only. The ten-minute rule now applies to **current schedule and publication checks**, including each independent SEC/IR component, at insertion; it does not expire a historical announcement. This supersedes the former two-minute publication and ten-minute PDF retrieval rules. Migration0106 enforces the new policy alongside existing immutable snapshots, probability guards and duplicate protection. Old tags are preserved but must not be used to bypass the current schema guard.

## Okta opening

Provided the reviewed December1 results date remains unchanged: **November16,2026 21:00 America/Los_Angeles = November17 05:00UTC**. Lock strictly before **December1 00:00 America/New_York = December1 05:00UTC**. “After market close” is not an exact publication time. Do not substitute the call time or16:00. Before the opening, the CLI skips; at the deadline it rejects. These are eligibility boundaries, not automatic jobs or authorization to execute a lock in this preparation pass.

Target: Q3FY2027, **August1–October31,2026**. Current stored range: **$813–817million**, guidance `7790a72a-98d9-57b3-9287-bf22cba52401` (August26 issuance/SEC availability, accession0001660134-26-000068). Seven eligible outcomes: below0 / within0 / above7. Empirical probabilities0/0/1; Laplace0.1/0.1/0.8. Both methods use the same selected inputs and cutoff. Refreshing input data may reveal a legitimate new block; these figures are not frozen future source checks.

## Owner checklist when official automated access fails

1. Before the short current-check window, update SEC facts and load only reviewed manual guidance. Review new input/evidence versions; extracted candidates remain quarantined. No Vertex or other model calls are involved.
2. Personally open the **exact** official announcement URL, news inventory and quarterly-results inventory below in your own browser. Check results **publication**, not a webcast/call. Cover every page/filter/year needed from target start through the actual check date, including preliminary results and schedule changes. Open relevant linked entries. A loading shell, inaccessible page, incomplete pagination or uncertainty is not a negative result; stop and record a gap.
3. Record each exact URL (and final URL if redirected), actual page-check timestamp with numeric UTC offset and IANA timezone, and second/minute precision. Do not copy the announcement's historical retrieval time into these fields, or use file/hash/entry time as page-check time. Record the actual automation failure URL/reason as owner-reported, without claiming an independently observed HTTP status unless supported.
4. Confirm the unchanged December1 after-close results schedule in America/New_York against durable evidence. If a date, timezone or publication interpretation changes, **stop**, preserve the observation and append/review a new durable evidence version. Do not edit prior evidence or label unknown timing verified.
5. Report target or preliminary results already public, contradictions, missing coverage or unresolved timing as a block. SEC absence alone is insufficient. Only attest `not_observed` if you actually completed all coverage. Identify yourself as the observer; browser observations are `user_verified`, not independently HTTP-verified by Codex.
6. Fill a copy of [owner_current_check_template.json](owner_current_check_template.json) outside the intake record directory. It intentionally contains null times and false/unknown observations. It is **not** an attestation. All observations must be supplied by you. The one schedule passage may cover multiple roles if that accurately describes your inspection; no invented duplicate evidence is needed.
7. Intake the completed form. It preserves original JSON bytes/hash and actual ingestion time; it never locks a prediction. Confirm assessment `usable`, correct target and original announcement ID. Blocked observations are also preserved; a latest blocked intake is not replaced by an older favorable one. Recheck pages honestly if the earliest page time will be older than ten minutes by insertion.
8. At or after the opening, manually invoke both-method locking only under separate live-lock authorization. The command performs its **own independent fresh SEC submissions check**, then revalidates owner freshness after the fetch. Failure or possible SEC results blocks. It records both methods atomically, with actual DB creation times and self-contained evidence. No `--as-of` option exists. Keep the execution output even for zero locks.

Official pages for Okta (check the entire relevant content):

- Announcement: https://investor.okta.com/news-and-events/news-releases/news-details/2026/Okta-to-Announce-Third-Quarter-Fiscal-Year-2027-Financial-Results-on-December-1-2026/default.aspx
- News and pagination: https://investor.okta.com/news-and-events/news-releases/default.aspx
- Quarterly results: https://investor.okta.com/financials/quarterly-results/default.aspx
- Independent SEC check, fetched by code: https://data.sec.gov/submissions/CIK0001660134.json

Run from the earnings worktree with the isolated `.venv`. Verify the checkpoint/schema first. Migration0106 must be applied. Dependencies remain pinned in `earnings/lock_ready/two_method_requirements.lock`; no shared environment changes.

```sh
# Before the short evidence window; review updated data before proceeding:
.venv/bin/python -m db.migrate
.venv/bin/python -m earnings ingest ALL --refresh
.venv/bin/python -m earnings load-guidance ALL

# After your actual checks; does not lock anything:
.venv/bin/python -m earnings.current_checks /absolute/path/completed-owner-check.json --directory data/cache/earnings/current-checks

# FUTURE MANUAL COMMAND ONLY: at/after Nov16 21:00 Pacific, with fresh usable checks:
.venv/bin/python -m earnings.predict --lock --methods both --owner-check-dir data/cache/earnings/current-checks
```

The default unique execution filename is printed and saved under `data/cache/earnings/lock-runs/`. With this directory, companies without an owner check use automated checks; an incomplete/stale owner record blocks instead of silently falling back. An explicit output filename must be new. Do not rerun a partial method pair with new inputs; the CLI blocks it for review. Duplicate protection includes method version.

## Limits and remaining real blockers

No owner-browser checks have actually been supplied. Actual source checks must be performed at the future lock attempt; this document, the old announcement, and synthetic rehearsals do not establish freshness. Historical evidence must still pass local integrity checks. Original CRWD/MDB owner PDFs remain outstanding. Missing dates for other companies remain unverified.

Human observations can be incomplete or mistaken; browser caching, wrong clocks, overlooked preliminary publication and incomplete inventories remain risks. Official sources plus SEC are not complete internet surveillance; a check-to-insert race remains. An attestation or SHA does not establish authenticity by itself. The DB protects ordinary application writes and immutable locked snapshots, not a DBA who changes enforcement or a dishonest operator. No eligibility, probability or outcome-quality guarantee follows from passing these checks.
