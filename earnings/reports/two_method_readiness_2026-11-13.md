# Manual-guidance two-method preparation

No live predictions exist or were created. The original empirical method remains `quarter-frequency-v1`; the separate fixed-prior method is `quarter-frequency-laplace-v1`, `(count+1)/(N+3)`. Input selection, cutoffs, eligible windows and fallback policy are identical. Each current company has enough own history, so no pooled fallback is used in this preparation. Full exact Decimal probabilities and historical IDs are in `earnings/validation/two_method_preparation_probabilities.json`; these are preparations, not immutable prospective predictions.

Counts are below/within/above. Fractions below express the formulas; stored values follow the existing 24-place half-even/residual convention.

|Company|N|Counts|Empirical|Laplace|
|---|---:|---|---|---|
|ADBE|8|0/0/8|0,0,1|1/11,1/11,9/11|
|CRM|8|0/4/4|0,1/2,1/2|1/11,5/11,5/11|
|CRWD|7|0/0/7|0,0,1|1/10,1/10,8/10|
|GTLB|7|0/0/7|0,0,1|1/10,1/10,8/10|
|IOT|8|0/0/8|0,0,1|1/11,1/11,9/11|
|LULU|8|2/0/6|1/4,0,3/4|3/11,1/11,7/11|
|MDB|7|0/0/7|0,0,1|1/10,1/10,8/10|
|OKTA|7|0/0/7|0,0,1|1/10,1/10,8/10|
|PD|7|0/3/4|0,3/7,4/7|1/10,4/10,5/10|
|S|8|0/1/7|0,1/8,7/8|1/11,2/11,8/11|

This is a fixed symmetric prior, not a tuned/calibrated forecast or Session6 model. Zero-history mathematical prior is unit-tested, but production history minimums still block empty history. Pooled fallback uses the same documented eligible pooled counts and receives the same fixed add-one prior.

## Manual future execution

After source refresh and manual guidance review, when a company is eligible:

```sh
.venv/bin/python -m earnings ingest ALL --refresh
.venv/bin/python -m earnings load-guidance ALL
.venv/bin/python -m earnings.predict --lock --methods both --output data/cache/earnings/lock-runs/two-methods-manual-unique.json
```

Choose a new output filename on each execution. The command uses actual PostgreSQL time, has no backdating option and does not schedule jobs. Both methods select one shared target, guidance, evidence, history and cutoff per company, then insert within one transaction; immutable creation timestamps are individually database-generated. Duplicate protection is per method. A partial existing pair blocks rather than silently choosing a different later cutoff for its counterpart.

|Company|Earliest opening (Pacific)|Conservative strict deadline|Remaining timing conditions|
|---|---|---|---|
|OKTA|Nov16, 2026 21:00|Dec1, 2026 00:00 America/New_York|Fresh announcement integrity and already-public checks at actual lock time|
|CRM|Nov17, 2026 21:00|Dec2, 2026 00:00 America/New_York|Same|
|IOT, S|Nov18, 2026 21:00|Dec3, 2026 00:00 America/New_York|Same|
|CRWD, MDB|Not yet established|Not yet established|Owner PDFs, official original URLs and retrieval times pending; expected Dec1 is not promoted|
|PD, GTLB, ADBE, LULU|Unverified|Unverified|Qualifying results-publication evidence still required; Adobe call listing is insufficient|

After-close wording is not an exact timestamp: lock strictly before the release date starts in the documented timezone. Source retrieval failure is not proof that no announcement exists. No company is claimed locked or automatically scheduled.

## Owner evidence

See `earnings/OWNER_EVIDENCE.md` and `python -m earnings.owner_evidence --help`. Original files are hashed/preserved in an ignored earnings-only cache. Intake records supplier, original official URL, owner-reported retrieval time and actual ingestion timestamp. Full-document review is separate; unresolved identity, period, dates or results-publication wording prevents promotion. Approved evidence is user_verified, not independently HTTP-verified. No PDFs were supplied during this preparation.

The former mandatory announcement HTTP refresh is explicitly replaced only for this owner-file route by an explicit owner-file route. A local integrity check does not refresh the source: owner-reported retrieval must still be within ten minutes, enforced in application code and migration0105. Older supplied files require a new actual owner retrieval/review version or a separately approved freshness-policy change. No blocked announcement HTTP download is required by that alternative route. The separate SEC + observable official-IR already-public-results check remains mandatory and may still block CRWD/MDB if the news inventory is inaccessible. We did not silently waive that gate or require the blocked announcement download as the only intake route. Earlier403 evidence stays intact.

## Validation and checkpoint

Migration0104 adds a Laplace-only probability/input guard without editing0103, its empirical reproduction, time windows, RLS, immutable snapshot protection, timestamp generation or method-specific unique key. Original empirical source is unchanged. Original-method fixed-input/time regression is byte-for-byte identical to `session3-lock-ready`; paired regression uses identical guidance/history IDs for each method. The new read-only actual-clock dry run uses PostgreSQL READ ONLY with insert adapters disabled: zero ledger rows before and after. Synthetic tests are not live predictions.

The separate two-method checkpoint will be recorded after the tested code commit. It is an agent-tested owner-authorized checkpoint pending owner review, not a claim of completed owner human review. `session3-lock-ready` remains at94984fc3ce33c6e85a287738d3a617561cd0cefc. Dependencies are pinned in `earnings/lock_ready/two_method_requirements.lock`; the only added package is pypdf7.0.1 in the isolated worktree `.venv`, never the deals environment. Freeze was completed November13, before November16,21:00Pacific. No merge, push or deployment.

Freshness correction: the initial preparation checkpoint87f48d4 allowed a fresh local hash check to stand in for source refresh. Before final delivery this was tightened: source retrieval freshness remains mandatory. The original preparation tag is preserved; a separate r2 checkpoint will freeze this correction, without moving session3-lock-ready.
