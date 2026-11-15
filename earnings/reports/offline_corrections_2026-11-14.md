# Bounded offline corrections — November14 Pacific

Owner-authorized scope: current-state policy separation, two cached validator defects, tests, read-only rehearsals and a new checkpoint. No provider/CountTokens calls, retries, fresh-set bodies/evaluation, human decisions, production promotion, website changes, live locks, merge, push or deployment. Existing tags and failed evaluations are preserved. This report is agent verification, not completed owner review.

## Current-state policy

`current-state-checks-v2`, enforced by migration0106, separates durable announcement provenance from fresh checks. Original PDFs/body hashes, original URLs and true retrieval/ingestion/verification timestamps are preserved. Local hashing receives a separate integrity timestamp; it neither re-retrieves nor authenticates a source. Historical announcements do not expire after ten minutes. The former two-minute publication and ten-minute owner-PDF retrieval conditions are superseded by the owner-approved **ten-minute current schedule/publication/SEC component checks** at DB insertion.

When automation fails, owner-browser records retain observer attribution, exact official URLs/final URLs, each actual observation time with timezone/precision, full schedule/news/results coverage, actual publication observation, contradictions and reported automation failure. Intake preserves original JSON by hash and generates its own actual receipt time. The earliest page observation controls freshness; blocked latest evidence suppresses older favorable evidence. No owner check has been supplied or invented. Code still performs a separate independent fresh SEC check, and SEC absence alone is insufficient. Incomplete, contradictory, stale, future, changed-schedule, already-public and unresolved checks block. Schedule changes require appended durable evidence and review. Existing source failures remain intact.

The database independently enforces the target/schedule agreement, component freshness, owner provenance/coverage/roles/timestamps and SEC manifest/clear status. It still generates creation timestamps, rejects backdating, protects self-contained immutable snapshots and prevents duplicates per method. Both-method insertion remains atomic. Administrator tampering, false attestations, cached/incomplete browser inventories, unobserved publication channels and the check-to-insert race remain residual risks; no complete internet surveillance is claimed.

The exact [owner checklist and commands](../CURRENT_CHECKS.md) and [empty template](../owner_current_check_template.json) are committed. The template contains no observed timestamps or attestation. Provided the schedule remains unchanged, Okta opens **Nov16 21:00 America/Los_Angeles / Nov17 05:00UTC**, with strict deadline **Dec1 00:00 America/New_York /05:00UTC**. This preparation does not authorize or schedule a prediction lock.

Future manual intake and locking, after actual owner checks and separate live-lock authorization:

```sh
.venv/bin/python -m earnings.current_checks /absolute/path/completed-owner-check.json --directory data/cache/earnings/current-checks
.venv/bin/python -m earnings.predict --lock --methods both --owner-check-dir data/cache/earnings/current-checks
```

Before that short window, apply migrations and refresh SEC actuals / reviewed manual guidance as documented in the checklist. No extracted candidate is a live input. Current remaining Okta blockers are the unopened window and **not-yet-performed** contemporaneous schedule/publication checks. At the future attempt, access, schedule changes, already-public results, stale inputs or missing/contradictory evidence can still block. Stored history has7 eligible observations, counts0/0/7; empirical0/0/1, Laplace0.1/0.1/0.8, unchanged. No prior-year growth block is inherited by the categorical target. Future outcome scoring requires its own comparability review.

CRWD/MDB owner files remain outstanding; their dates have not been promoted. Other unresolved release dates stay unverified. Verified next openings retained in the actual-clock report: CRM Nov17 21:00Pacific; IOT/S Nov18 21:00Pacific. No automatic jobs exist.

## Verification evidence

- **Full suite:**549 passed,3 skipped,2 xfailed. Earnings subset326 passed,2 xfailed. The two frozen-v1 ARR/implied-quarter expected failures are unchanged, not counted as repaired behavior. No expected-failure tests were weakened or removed.
- **17-case boundary rehearsal:** [stored output](../validation/current_checks_v2_read_only_rehearsal.json). PostgreSQL READ ONLY; insertion is captured in memory, source checks are synthetic, no HTTP/provider calls. At opening−1microsecond:outside window; at opening and+1microsecond:two conditional methods with identical guide/history/cutoff; at deadline:blocked. Complete synthetic owner+SEC checks yield two conditional methods while preserving the old durable timestamp. Stale/incomplete/changed/already-public checks block. These conditional cases are not live records and do not establish actual future source access.
- **SQL enforcement tests:** real PostgreSQL tests use current DB time, synthetic evidence and transaction rollback. Old durable owner PDF plus fresh complete owner+SEC checks admits both methods in the test transaction; forged coverage, schedule, publication, contradictions, stale page/SEC, possible SEC results and missing roles reject. Existing UPDATE/DELETE/TRUNCATE, snapshot, duplicate, backdating and probability tests pass. No simulated creation time is supplied to production insertion.
- **Fixed-input/time regressions:** [identical original and two-method results](../validation/current_checks_v2_fixed_regressions.json) against94984fc and7dc952c. Compare exact guidance/history IDs, target, probabilities, method, eligibility and rejection reasons. These adapters bypass SQL insertion; new-policy SQL tests separately cover intentionally changed current-state enforcement.
- **Actual-clock read-only run:** [output](../validation/current_checks_v2_actual_clock_dry_run.json), executed2026-11-15T00:23:10UTC (Nov14 Pacific); zero rows before/after, four outside-window companies and six unverified release dates. No live source checks dispatched because none is in its window. No claim of fresh source verification.
- **Final integrity:** [guard/tag/accounting evidence](../validation/current_checks_v2_final_integrity.json). All three installed0106 function bodies match final migration source. Zero live predictions and zero scores. Original baseline, Laplace math, historical selector and scoring modules unchanged. Previous tags retain exact targets. No dependencies installed/upgraded; existing isolated dependency lock SHA256724e79d85f370754531901af2f5c65d07f4b98ef24acffb60e6dddfde0c6b527.

A new `session3-current-state-v2-lock-ready-20261114` checkpoint is created only after the checks above; the accompanying `lock_ready/current_state_v2_checkpoint.json` records its exact code commit. Earlier tags remain intact. Older code does not supply the new current-check snapshot shape and is intentionally incompatible with0106 locking; do not disable the guard to run old code. The new tag freezes code, not future evidence or timestamps, and is not a claim of completed owner review or a passed prospective live gate.

## Cached-response repair (not fresh performance)

Prior range evidence validity is now separate from its own unknown revision status. Currency, amount, company, scope, metric, basis/qualifiers, fiscal period, source/evidence and availability checks still apply. A supported earlier range can support a comparison without inventing an “initial” status. Unsupported/withdrawn ranges cannot. ADI's missing start is filled only from an existing calendar when every provided boundary agrees; conflicting/unknown calendars block.

[New revalidation artifact](../validation/hybrid_post_diagnostic_validator_repair_v1.json) maps original IDs/failures to repaired IDs and preserves original raw/request/result/evaluation/review hashes. Original21 rejected current proposals become **20 rejected +1 human-review-flagged;0 accepted**. The5 prior-context observations remain separate. All16 numeric reference ranges were proposed by the saved responses, but none is accepted or human-validated. Two additional eligible-looking annual proposals remain outside the original positive-only reference scope, and3 proposals are intentionally noneligible. Numeric agreement is not semantic correctness or record-level quality. Human review remains pending; the original88-minute packet/sampling is unchanged, with this repair report as an addendum. No unfavorable sample was replaced.

| Diagnostic company | Current rejected | Current flagged | Accepted | Prior-context observations |
|---|---:|---:|---:|---:|
| Agilent |1|1|0|2|
| ADI |1|0|0|0|
| AMAT |1|0|0|0|
| DocuSign |2|0|0|0|
| Five Below |2|0|0|0|
| Hims |2|0|0|1|
| Teladoc |2|0|0|2|
| Zoom |4|0|0|0|
| Samsara |3|0|0|0|
| CrowdStrike |2|0|0|0|

Exactly three current records change:

- **Agilent annual$6.73–6.81B:** removes `INVALID_STATUS_REFERENCE_INPUT` caused solely by the prior range's unknown status. Its current comparison passes deterministic checks but remains quarantined/human-review pending. Prior status stays unresolved; no range is labeled initial.
- **ADI Q4FY2024$2.40B±$100M:** fills August4–November2,2024 from the existing registered calendar; removes `CALENDAR_BOUNDARY_MISMATCH`, retains `UNRESOLVED_STATUS`. Boundaries derive from already-preserved Q3/Q4 release evidence, accessions0000006281-24-000158 and0000006281-24-000202, not invented calendar dates or a synthetic actual amount. Original model start remains null in the proposal/audit trail. Exact period/source evidence: `pilot_s5/calendars.json`, ADI2024:4.
- **Hims annual:** prior range's unknown status no longer invalidates its amounts, but `INCOMPARABLE_STATUS_REFERENCE` remains for differing scope qualifiers. No silent acquisition normalization.

Repeated/missing quote matches, metric/scope/source failures, table headers/column support, units/basis ambiguity and unsupported statuses remain blocked. Deterministic quote location is not semantic proof. The archived pre-repair validator/config/freeze and all original failed outputs remain unchanged. Active config is a **new paused offline-repair version**; generation prompt/schema/settings were not changed or used. Cached revalidation does not count as a new successful extraction or fresh held-out result.

Reproduce offline without ledger writes:

```sh
.venv/bin/python -m earnings.hybrid.revalidate_cached --output /tmp/crosscheck-new-repair-analysis.json
```

## Accounting and stop

Persistent attempt/event hashes unchanged;11 historical attempts,0 active. **$8 operational ceiling**, accounted$0.363525, unresolved reservations$2.2373935 (including original$1.12), occupancy$2.6009185, headroom$5.3990815. Known-counter subtotal$0.9593205 is informational and not added to reservations. No reservation released or reset, no new event/call/charge. This ledger ceiling is **not a provider billing cap**, and shared Cloud credit remains uncertain.

Stop for owner review. No inference, fresh-set work, production promotion or live prediction has been performed in this correction pass.
