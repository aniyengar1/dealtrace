# Manual tracker:17-day entry policy and extractor shelving

**No live predictions were created.** The planned owner lock session remains **Monday, November16,2026 after9p.m. America/Los_Angeles** (November17 after05:00UTC). Earlier eligibility does not authorize earlier execution. No scheduler, provider/CountTokens calls, extraction tuning/review, fresh-set evaluation, production promotion, website changes, merge, push or deployment occurred.

## Precondition and actual policy change

The first READ ONLY check found **zero live predictions** at **2026-11-15T03:04:41.413913UTC**, before any policy edit. Old entry window:14 days. New entry window:17 release-local calendar days. Version **`live-entry-17-calendar-days-v1`**; code-policy edit timestamp **2026-11-15T03:06:29.923377UTC**. Migration0107 applied at **2026-11-15T03:25:01.951820UTC**. It takes an exclusive ledger-table lock and refuses the change if any prediction exists, preventing a concurrent first insert from racing the zero-row precondition.

Reason: operational convenience, permitting the single planned November16 after9p.m. Pacific session. This precedes the first live lock and uses no future outcomes. Final READ ONLY check at **2026-11-15T20:43:59.057776UTC** again found **zero predictions and zero scores**. Actual timestamps are preserved; no verification or prediction was backdated.

Python and the common PostgreSQL prediction guard both enforce the new opening. Calendar subtraction occurs in the documented release timezone, then converts to UTC; local midnight remains midnight across DST. Start-of-release-date deadlines remain unchanged for date/after-close evidence. Both frozen methods use the same window.

The original D−15 guidance/historical horizon remains unchanged. Early entry additionally caps selected live guidance by **actual public availability** (`min(D−15,current New York date−1)` for day-precision issuance/filing intervals). Otherwise the extra early days could select not-yet-public records. This does not change selection after the old opening or retune historical observations. The original empirical/Laplace modules, probability math, historical selector and outcomes are byte-for-byte unchanged. Locked snapshots record the new operating-policy version/opening; they remain immutable.

## Verified schedule records and planned session

These are existing verified durable announcements, **not freshly rechecked schedules**. All require fresh schedule/publication/SEC checks at the actual lock attempt.

| Company | Current release date | New opening Eastern | New opening Pacific | Unchanged strict deadline Eastern | Existing announcement evidence ID |
|---|---|---|---|---|---|
| Okta | December1 | November14,00:00 | November13,21:00 | December1,00:00 |4a3e1f16-7b0b-55be-b00b-f43055db57af|
| Salesforce | December2 | November15,00:00 | November14,21:00 | December2,00:00 | See `announcements/CRM.json` latest reviewed version |
| Samsara | December3 | November16,00:00 | November15,21:00 | December3,00:00 | See `announcements/IOT.json` latest reviewed version |
| SentinelOne | December3 | November16,00:00 | November15,21:00 | December3,00:00 | See `announcements/S.json` latest reviewed version |

Timezones: America/New_York / America/Los_Angeles (EST/PST). All four are within the **timing** window at the planned session, conditional on every other gate. CrowdStrike/MongoDB would share the December1 opening **only after their announcement evidence is accepted**; owner PDFs are still outstanding and neither is promoted. PD/GTLB/ADBE/LULU also retain unverified results-publication dates. “Unverified” does not mean “not announced.” No date checks or owner attestations were invented.

## Tests and rehearsals

**Full suite:569 passed,3 skipped,2 preserved expected failures.** The two frozen-v1 extractor failures are unchanged, not repaired/reviewed in this pass. No expected-failure test was removed or weakened.

- New targeted tests:22 passed, including the existing current-check boundary tests. Immediately before/at/after each of the three new openings, and immediately before/at the unchanged deadline, Python/SQL opening calculations agree. All ten companies are exercised with both methods using clearly synthetic, non-persisted fixtures. SQL tests use the actual database clock and rollback transactions to admit both methods during the additional interval, reject outside-window/deadline attempts and reject not-yet-public guidance. DST crossings preserve the release-local calendar. Initial fixture offset/past-date assumptions were corrected to match timezone semantics; production evidence/clock requirements were not loosened.
- [Fixed-input regression](../validation/entry17_fixed_regressions.json) compares prior checkpoint `c2c587fdeb550b7afe70a1a54098299d8874589e` with current code using the same25 fixed cases. **42 shared method candidates match exactly** for guidance/history IDs, probabilities, target and method; **193 common rejection records match semantically**. All72 newly admitted method-cases fall strictly in the additional three-day interval; these are repeated synthetic scenarios, not72 predictions or companies. No common eligible candidate was lost.
- Intended diagnostic metadata changes: outside-window code renamed from obsolete `OUTSIDE_14_DAY_WINDOW` to `OUTSIDE_LOCK_WINDOW`; its next-eligibility timestamp moves three days earlier. Policy/version metadata and immutable snapshot description identify the new rule. Tests normalize only this rename and opening metadata. **No unexpected differences** in common outputs or blocking behavior.
- [Boundary/planned-session READ ONLY rehearsal](../validation/entry17_boundary_read_only_rehearsal.json):17 boundary/failure scenarios plus4 planned-session company cases, both methods. Hypothetical source checks are explicitly synthetic. At planned November17 05:00:00.000001UTC, OKTA/CRM/IOT/S each produce2 conditional candidates with identical shared guidance/history/cutoff. This proves timing/data-path readiness, not actual source freshness, live creation or a passed prospective gate. Source/publication/stale/incomplete/schedule blocks remain active. Database ledger count0→0; inserts captured in memory, production timestamp insertion never executed with test time.
- [Actual-clock READ ONLY dry run](../validation/entry17_actual_clock_dry_run.json), started **2026-11-15T07:40:56.912258UTC**:OKTA/CRM in-window but blocked `READ_ONLY_CURRENT_CHECK_REQUIRED`; IOT/S outside until November16 05:00UTC; six dates unverified. Offline source callbacks prohibit HTTP; no real verification claimed. Ledger0→0, all writes suppressed independently by READ ONLY.
- [Final integrity](../validation/entry17_final_integrity.json):both installed0107 function bodies match final source; previous tags, pinned dependency lock, baseline/history/scoring/current-check/owner-evidence files and manual guidance/announcement files unchanged. No dependencies changed. Database-generated timestamps, UPDATE/DELETE/TRUNCATE protections, self-contained snapshots, duplicate-per-method protection, comparability/source/freshness/withdrawal checks and independent SEC/already-public checks remain in force. A DBA can still alter enforcement; no stronger administrator threat model is claimed.

## Owner checklist and exact future command

Use [CURRENT_CHECKS.md](../CURRENT_CHECKS.md), updated with the uniform17-day table and planned-session restriction. Preserve original durable files/URLs/hashes/timestamps. Historical PDF age is not current-check age. Personally check the exact official announcement, news and results inventories; supply genuine coverage/timestamps/attribution only if automation fails. Missing/changed/contradictory/already-public/unresolved evidence blocks. All current components remain <=ten minutes at insertion, plus the independent fresh SEC check; SEC absence alone is insufficient.

Before the short evidence window, refresh actuals/reviewed manual guidance and apply migrations through0107. Intake the actual owner check, then **during the planned November16 after9p.m. Pacific session and under live-lock authorization**, run manually:

```sh
.venv/bin/python -m earnings.current_checks /absolute/path/completed-owner-check.json --directory data/cache/earnings/current-checks
.venv/bin/python -m earnings.predict --lock --methods both --owner-check-dir data/cache/earnings/current-checks
```

No one has supplied a current owner attestation in this pass. Do not execute earlier merely because a company is eligible. No future process is waiting or scheduled.

New checkpoint: `session3-entry17-lock-ready-20261115` (exact code commit recorded in `lock_ready/entry17_checkpoint.json` after tagging). It is owner-authorized and agent-tested, not a claim of final owner acceptance or a passed live gate. All prior tags remain intact; their older timing enforcement is superseded. Do not disable newer DB guards to run old code.

## Extractor shelved and budget preserved

Owner extraction review: **deferred, not performed**. Administrative status is in [EXTRACTION_STATUS.md](../EXTRACTION_STATUS.md) and `hybrid/STATUS.json`. Historical pending labels remain unchanged audit states. All original splits/fresh reservations, failed evaluations, raw responses, cached repair outputs, prompts/rules and the original random review packet remain preserved. Fresh evaluation bodies/labels/inference remain untouched. No extracted candidate enters manual guidance or live inputs. No tuning, inference or extraction review is authorized.

The$8 operational ceiling remains unchanged. Accounted$0.363525 + unresolved reservations$2.2373935 = occupancy$2.6009185; headroom$5.3990815. The original$1.12 reservation remains held. Attempt/event hashes match the prior checkpoint; no new cost events or charges. Known-counter subtotals are not additional charges. The local operational ceiling is **not a provider billing cap** or a guarantee of shared trial credit.

Stop for review. No live predictions, automatic locks, merge, push or deployment.
