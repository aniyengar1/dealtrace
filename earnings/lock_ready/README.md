# Preserved Session 3 lock-ready workflow

Local annotated tag **session3-lock-ready** resolves to **94984fc3ce33c6e85a287738d3a617561cd0cefc**. Verify with `git rev-parse 'session3-lock-ready^{}'`; do not move an existing tag. Session 4's ordering exception does not mark the prospective live gate passed.

`environment.json` records Python **3.14.7**, the existing isolated worktree `.venv`, platform and dependency fingerprints. `requirements.lock` pins all installed direct/transitive versions; the existing top-level requirements were not changed. No dependency was installed or upgraded in Session 4. To reconstruct elsewhere, create an isolated venv with the recorded Python and install `-r earnings/lock_ready/requirements.lock`; psycopg and psycopg-binary are pinned binary builds. Reproduction on another OS may require compatible binary wheels; do not reuse Claude's shared environment.

The tag freezes **code, not live evidence**. Actual locks must refresh SEC facts, manually reviewed guidance versions, results-announcement evidence and already-public-results checks, and use the actual PostgreSQL clock. Do not lock from the historical files copied into an old archive without refreshing current data and checking schema compatibility.

## Review harness

`check.py` is external to the lock import graph. It does not modify production modules on disk. The read-only adapter suppresses history INSERTs and captures proposed ledger INSERTs as research diagnostics. PostgreSQL `BEGIN READ ONLY` is a separate write barrier; all connections roll back. No prediction ID or made_at is fabricated, and `locked` is always empty. Missing unimported history versions are reported rather than silently inserted. It checks that required earnings migrations already exist and then exercises production queries against the schema.

```sh
.venv/bin/python earnings/lock_ready/check.py --code-root . --output /tmp/crosscheck-dry-run-new.json
```

For the reviewed version, the session used a `git archive session3-lock-ready` copy under `/tmp/crosscheck-lock-ready-94984fc`; it did not change either active worktree or branch. Run the same external harness with `--code-root /tmp/crosscheck-lock-ready-94984fc`. The harness loads required environment variables through python-dotenv from the active worktree; it never prints them. It uses the same pinned isolated interpreter for both code copies.

`--regression` instead runs explicitly **synthetic fixed-input/time tests with no database or HTTP access**. It compares outside/inside windows, deadline equality, withdrawn guidance, stale actuals, already-public results and missing history. Its proposed candidates are not live predictions and cannot be scored as live. The committed tag/HEAD outputs are identical for eligibility, target periods, exact guidance and historical input IDs, probabilities, method and rejection reasons. All 64 protected code/data/schema files and the installed dependency freeze match the reviewed tag. No imported lock module changed in Session 4.

## Next manual live windows

All four verified releases have after-close wording, not exact results timestamps. Timezone **America/New_York**; these dates are EST (UTC−05:00). Lock strictly before the start of the release date, never 16:00 or a call time.

| Company | Window opens | Strict deadline |
|---|---|---|
| OKTA | Nov 17, 2026 00:00 EST / 05:00 UTC | Dec 1, 2026 00:00 EST / 05:00 UTC |
| CRM | Nov 18, 2026 00:00 EST / 05:00 UTC | Dec 2, 2026 00:00 EST / 05:00 UTC |
| IOT | Nov 19, 2026 00:00 EST / 05:00 UTC | Dec 3, 2026 00:00 EST / 05:00 UTC |
| S | Nov 19, 2026 00:00 EST / 05:00 UTC | Dec 3, 2026 00:00 EST / 05:00 UTC |

CRWD/MDB remain unverified because full direct-source retrieval was blocked; ADBE's call is insufficient; PD/GTLB/LULU remain unverified. A missing verified date does not mean an announcement does not exist. No automatic scheduler or future waiting process exists.

When eligible, follow the source-refresh/review steps in `earnings/reports/session3_evidence_review_2026-11-12.md`, append evidence versions if sources changed, then manually run:

```sh
.venv/bin/python -m earnings ingest ALL --refresh
.venv/bin/python -m earnings load-guidance ALL
.venv/bin/python -m earnings.predict --lock
```

Session 4 candidates are intentionally not production inputs. The lock command rechecks the actual time and all rejection gates, generates a uniquely timed execution record and permits zero locks. A dry run does not satisfy the prospective gate. No merge, push, deployment or Session 5 work is authorized here.


## November13 two-method checkpoint

Use **session3-two-method-lock-ready-20261113-r2** at **7dc952c635446bb4ed3a6717d58cb7dc003f62cb** for the owner-authorized empirical+Laplace workflow. The earlier preparation tag at87f48d4 is preserved, superseded by r2's explicit owner-source freshness guard. Neither tag is a claim of completed owner human review. Original `session3-lock-ready` remains at94984fc3ce33c6e85a287738d3a617561cd0cefc. Frozen dependencies are in `two_method_requirements.lock`; the only added package is isolated pypdf7.0.1.

The methods share guidance/evidence/history and a probability cutoff; actual creation times remain database-generated. Use `python -m earnings.predict --lock --methods both` manually when eligible after current source refresh and review. There are still **zero live predictions**. No scheduler exists.

Owner PDFs are intake-ready, but CRWD/MDB files are pending. Approved owner evidence uses its actual reported retrieval time for the ten-minute source-freshness gate; a new local hash check cannot freshen it. A new genuine owner retrieval/review version or explicit policy change is needed if stale. The separate SEC+official-news already-public check is still mandatory and may block inaccessible inventories. Details: `earnings/OWNER_EVIDENCE.md` and `earnings/reports/two_method_readiness_2026-11-13.md`.

## November14 current-state policy checkpoint

The owner-authorized `current-state-checks-v2` checkpoint supersedes the old retrieval-age rules above. Durable files retain their true dates; fresh current schedule/publication and independent SEC checks have ten-minute limits. Historical tags remain intact, but their older insertion shape is intentionally incompatible with migration0106's current-check guard; use the new checkpoint for actual locks. Do not drop the new guard to run old code. See [CURRENT_CHECKS.md](../CURRENT_CHECKS.md) and the current-state review report for the new tag/hash, checklist and commands. Existing baseline math and financial selection are unchanged and tested against both older checkpoints. No dependencies changed in this correction pass.
