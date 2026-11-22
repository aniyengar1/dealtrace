# Bounded v2 rule repair — no production promotion

The original v1 rules, split, gold, outputs, scores and two expected-failure tests remain unchanged. V1's former holdout is **diagnostic/regression data**, not fresh evaluation data for v2. Candidates and review partials remain separate from production guidance and the live baseline. No LLM inference calls were made.

## Reservation and freeze order

1. **18ef3b1** reserved the new evaluation procedure and exact issuer/release groups before rule changes. For each of the existing ten issuers, select the latest original Item 2.02 8-K from April–July **2023**, plus its immediately preceding earnings release as context. All related source versions stay in one issuer group; context is never development data. A metadata-only 2024 proposal was rejected before reading its release bodies because annual target periods overlapped already exposed later guidance. No selection was made based on rule performance.
2. Repair v2 using only the old development and former-holdout diagnostics. **19cfaa5** froze `rules.py`, `pipeline.py`, `corpus.py`, evaluator and package initialization before opening the reserved release bodies. `rules_frozen_v2.json` pins these files and the reservation.
3. Read all 20 reserved source releases through the existing SEC fetcher after freeze. Manually transcribe/review every annual and directly issued next-quarter consolidated revenue target in the ten evaluation releases. Context supports status comparisons but is not scored. **bef0fbb** committed the 20 gold records before extraction evaluation. Gold SHA-256: `cf19649ba9f901bf8245410a3d844f407998c835584bbb4599c83b44a7bc7e4c`.
4. Run the fresh evaluation **once**. Do not tune further on this set or describe a replay as fresh held-out performance. Rule hashes are unchanged after evaluation.

The curator had prior exposure to these issuers, later formats and historical companyfacts. The reserved 2023 release bodies and guidance target periods were not used to develop v2. Labels were manually reviewed independently of the extractor and mechanically crosschecked against pinned SEC quotes, Decimal scaling, datelines and annual XBRL fiscal-boundary records. This is one curator, **not** independent two-human adjudication or an external blind issuer test. Quarterly `initial` means first direct range observed in the reserved release group; `original_verified=false` explicitly avoids claiming exhaustive original-guidance history. Twenty labels/eighteen outputs cannot substantiate a general 98% precision rate.

## Repair behavior

- Parse HTML revenue rows with their full column headings, unit context and nearby outlook introduction. `Annual recurring revenue`, ARR and other non-consolidated labels are excluded before amounts enter candidate history.
- Preserve column alignment across direct and implied periods. An implied/derived column is explicitly skipped; it cannot become a directly issued quarterly guidance candidate or a status-history input.
- Prose uses its own fiscal context. Explicit bare-year outlook clauses such as “For 2026,” are annual; ambiguous mixed-target prose abstains instead of borrowing a preceding quarter.
- Status comparisons require the same company, metric, fiscal bounds, basis and units, and a non-future, directly issued prior revenue observation. Keep exact prior candidate IDs and comparison evidence. An unresolved annual initial/revision status produces a **partial plus abstention**, not a guessed initial record.
- Explicit reaffirmations/high-end references can carry a numeric range only from matching prior evidence. No missing value becomes zero. Unknown or mixed revisions remain review items.
- Candidate quotes are literal half-open Unicode offsets into retained canonical text. Evidence also retains table headers, row context, surrounding text, dateline/primary evidence, raw body hashes and canonical hashes. Quote matching alone does not establish semantic correctness; issuer calendar/basis assumptions are still documented manual metadata.

The expected-failure tests remain tests of frozen v1, and still xfail. Separate ordinary v2 tests pass for the repaired ARR and implied-column cases. They do not mean all v1 behavior or all semantic edge cases are repaired.

## Scores

| Dataset | Correct / emitted / gold | Strict precision | Strict recall |
|---|---|---|---|
| Old development | 89 / 89 / 96 | 100% | 92.71% |
| Former holdout, now diagnostic | 33 / 33 / 38 | 100% | 86.84% |
| New reserved releases, evaluated once | 18 / 18 / 20 | 100% | 90% |

Every emitted record matched all strict fields. Missing records remain false negatives: explicit abstention improves precision at the cost of recall. Fresh misses are Adobe's annual raise (the immediately preceding context did not supply an annual revenue range) and lululemon's annual raise (the earlier “For fiscal 2023, we expect” context was not resolved). The manual source supports both labels; these are parser limitations, not unavailable company evidence. Do not repair them after inspecting fresh results and keep calling the set fresh.

Fresh precision and recall **meet the stated numerical cutoffs on this small sample**. The user's conditional requirement to write an LLM/hybrid proposal if fresh precision <98% OR recall <90% was therefore not triggered. No hybrid extractor, model call, quota use or production promotion was implemented. The old diagnostic subset still has recall below 90%; broader quality is not established. Stop for review/architecture discussion; Session 5 remains blocked.

Detailed field metrics, per-company results, every miss, source/version evidence, partials and rejection counts are in `earnings/validation/session4_repair_*.json`. Raw rejection counts include non-target ARR rows and unjudged old-source contexts; they are not a count of gold false negatives.

## Reproduce without changing inputs

```sh
.venv/bin/python -m earnings.extraction.v2.verify_gold --output /tmp/repair-gold-check-new.json
.venv/bin/python -m earnings.extraction.v2.evaluate --dataset development --output /tmp/repair-dev-replay-new.json
.venv/bin/python -m earnings.extraction.v2.evaluate --dataset old-heldout-diagnostic --output /tmp/repair-diagnostic-replay-new.json
.venv/bin/python -m earnings.extraction.v2.evaluate --dataset fresh --output /tmp/repair-reserved-set-replay-new.json
.venv/bin/python -m pytest tests/earnings/test_extraction_v2.py -q
```

All output paths must be new. The `fresh` argument is a fixed dataset name; after this run, subsequent executions are **replays**, not new independent fresh evaluations. Preserve the pinned source cache/manifest versions and hashes; never substitute edited gold. No outputs are read by production guidance loaders. No changes to Session 3 eligibility, baseline probabilities, production data or schemas are part of this pass.
