# SYNTHETIC — twelve-prediction scoring/publication rehearsal

Actual execution: **2026-11-23T20:08:43.884407+00:00–2026-11-23T20:08:44.904024+00:00**. No real results, owner outcome review, live scores or new locks.

The READ ONLY export contains 12 predictions for OKTA, CRM, IOT, S, GTLB and CRWD, two frozen methods each. Original IDs, timestamps, guidance, snapshots and history were copied unchanged into TEMP views. No prediction was inserted into either the live ledger or scratch public ledger.

## Results

- **12/12 scored**; **0 duplicates** on the second pass.
- Future evidence rejected.
- Scored SQLite export and public-shaped JSON regenerated; all 12 published records have one reviewed-shaped synthetic score.
- Valid marked synthetic SQL seed generated from the explicit output directory, applied twice idempotently in the scratch publication-copy tables, and read back exactly through `dealtrace_web`. INSERT/UPDATE/DELETE/TRUNCATE denied to that role.
- Public scratch prediction/result tables remain empty; scores are TEMP-only. No production seed, snapshot table or site data changed.

| Company | Fabricated actual USD | Outcome |
|---|---:|---|
| OKTA | 812,000,000 | below |
| CRM | 11,420,000,000 | within, lower endpoint |
| IOT | 517,000,000 | above |
| S | 311,000,000 | within, upper endpoint |
| GTLB | 282,000,000 | within |
| CRWD | 1,526,200,000 | within |

## Timing guard and explicit scratch simulation

The first real-clock attempt stopped correctly: November22 locks need a later synthetic release dated November23, whose conservative filing-day availability closes November24 at05:00UTC. It is impossible to both retain those locks and score that day-precision synthetic evidence at the actual November23 execution time. No failure was suppressed or production guard loosened.

The successful run explicitly used **2026-11-24T05:00:01+00:00**, a forward-only test clock confined to the scratch scorer's clock query and copied TEMP result trigger's timestamp assignment. Every other validation in the copied trigger, source verifier and scorer remained unchanged. The production scoring module, SQL migrations and original timestamps were untouched. Execution timestamps above and read-only export timestamps are actual wall time. Synthetic score timestamps are simulated future test values, never live results.

## Integrity and timings

READ ONLY checks before **2026-11-23T20:08:42.853577+00:00** and after **2026-11-23T20:08:45.069625+00:00** returned identical prediction/result/history records: **12 predictions, 0 scores**. Ledger hash both times: `88a79055f4e112bc3160d14022dad01057a1a131d76dd807ac7cbfea7f03c3f2`.

Automatic timings: migrations 0.2607892081141472s; scoring/repeat 0.45179999992251396s; archive/export/seed/read 0.15271625015884638s. No human review was performed or timed. Real data publication latency and comparability remain untested by synthetic fixtures.

Sanitized evidence: `earnings/validation/scoring_pipeline_rehearsal_twelve_2026-11-23.json`. Raw archives, fabricated review files and generated SQL remain in the ignored private rehearsal cache. The failed initial attempt remains there separately. No provider calls, new locks, live-ledger writes or push.

## Regression checks

Bare `python -m pytest -q` from the repository root, isolated scratch DATABASE_URL: **833 passed, 4 skipped, 2 xfailed in 9.27s**. Added tests cover the narrow scratch clock query override, rejection of backdated simulation before any database connection, and the actual newly-locked/day-availability boundary. The two known extractor expected failures remain unchanged.
