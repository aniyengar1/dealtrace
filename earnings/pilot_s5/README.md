Bounded Session 5 pilot: **quality gate FAILED; no expansion or promotion**. This directory is research evidence, not the production company registry. Raw filings, all actual versions, candidates and the assembled dataset remain under gitignored `data/cache/earnings/pilot_s5/`. Tracked sample/gold/source manifests preserve the audit. No model inference, dependency installation, schema change, website change or production-guidance write occurred.

Selection was recorded in commits52ab4f6/b05bfc7/68ae42e before extraction; the final20-company roster/exclusions in800cf6c; the fixed30-release sample/inventory ina74fe37; manual gold and calendar metadata in4c9aed1 before the first evaluation. Existing v1/v2 rules, evaluations and original manual gold were preserved. All new files are earnings/ or tests/earnings/.

Use the existing isolated worktree `.venv`; Python and all dependency versions remain pinned in `earnings/lock_ready/environment.json` and `earnings/lock_ready/requirements.lock`. No shared Claude environment changes. See the detailed report under `earnings/reports/session5_pilot_2026-11-13.md`.

```sh
# Resumes SEC downloads from retained cache; refuses frozen inventory/sample drift.
.venv/bin/python -m earnings.pilot_s5.collect
# Source-only packet; no extractor outputs included.
.venv/bin/python -m earnings.pilot_s5.review
# REPLAY of consumed sample, never fresh evaluation. Use a new output path.
.venv/bin/python -m earnings.pilot_s5.evaluate --output /tmp/session5-v2-replay-new.json
.venv/bin/python -m earnings.pilot_s5.assemble
.venv/bin/python -m earnings.pilot_s5.coverage
.venv/bin/python -m pytest tests/earnings/test_pilot_s5.py -q
# Explicit PostgreSQL READ ONLY barrier; cannot lock predictions.
.venv/bin/python earnings/lock_ready/check.py --code-root . --output /tmp/session5-lock-dry-new.json
```

Do not rerun `seal_gold` or `result_audit` over existing sealed evidence; they refuse overwrite. Corrections require separately identified evidence versions and a transparent recomputed diagnostic score, never relabeling an inspected sample fresh. `evaluate` verifies the frozen v2 hashes, manual-gold seal, pinned raw source hashes and literal quote offsets. It invokes frozen v2 with a separate pilot-only calendar registration context, restores its globals afterwards, and writes no database records.

The calendar adapter is an explicitly declared metadata extension, **not unchanged out-of-box v2 issuer coverage**. It supplies exact fiscal bounds from original SEC facts; a monthly calendar policy only when original annual boundaries consistently agree; two explicit source-reviewed quarter supplements. It does not change financial wording, metric/status rules, or the original10 calendar results. Unknown future weekly bounds abstain. The analysis is retrospective; later-known calendar metadata is not asserted to have been available at a historical live lock. All model/live inputs remain protected and separate.

`inventory` pairs the preceding earnings release with a following result, up to8 target-quarter groups per issuer. Same-release amendments are grouped; preliminary releases are retained in the cached source inventory. This is not a guarantee that every intraquarter Item7.01 revision was discovered or that the result filing was the first public announcement. `coverage` initially mapped152/160 physical target periods using reported date evidence and registered bounds;150 had a selectable raw companyfact/compatible Q4 derivation. A separate source/fact inventory review in `coverage_reviewed.json` completes all160 periods and156 raw actual matches, preserving the initial artifact. Six Jabil headings match original10-Q fiscal bounds, and Sanmina/Plexus Q4 boundaries preserve98/91days respectively. This review does not alter extraction/gold/calendars or scores. These are inventory counts, **not verified outcomes**. Missing actuals and unreviewed comparability remain blocks; raw fact availability is not a reconciliation pass. The fixed sample includes one release with annual-only guidance rather than replacing it. Full guidance content in each sampled release was reviewed for all annual/quarterly revenue targets, including historical-reference and non-revenue columns;49 targets were sealed, with no candidate output seen during labeling. Seven explicit USD tolerances have labeled arithmetic endpoints; one annual point target retains equal endpoints. No synthetic range is invented for points or percentage-only tolerances.

`assemble` preserves all selected-concept actual versions and IDs in isolated cache, chooses original available target-period facts for audit rather than silently replacing them with later restatements, and retains raw scales even when wrong.24 manual quarterly audit outcomes are reconciled,5 remain blocked;130 other release groups have no manual result approval. These labels are retrospective audit evidence, not live scores or automatically approved ML training rows. See `architecture_proposal.md` for proposed next steps only. Broader collection requires user review.
