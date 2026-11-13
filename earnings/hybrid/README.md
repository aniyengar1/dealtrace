Crosscheck hybrid diagnostic — **authorized probe stopped; owner review required**.

One existing Agilent release was processed on November 13, 2026. Vertex returned the requested model, but `thoughts_token_count` was null. The accounting gate stopped continuation: one inference attempt, no retry, nine releases not run. Do not rerun inference to resolve this. The raw response and full $1.12 reservation remain in the earnings-only ignored cache/SQLite ledger. See [probe report](../reports/hybrid_diagnostic_probe_2026-11-13.md).

The owner explicitly authorized concurrent diagnostics while the deals run continues and accepted residual billing uncertainty. This superseded the earlier wait and documented combined-bound prerequisites. Historical preparation records are preserved under `archive/pre_authorized/`. We have not read or changed the deals checkout or run files.

Configuration remains Vertex (`vertexai=True`), project `just-rhythm-506202-j8`, global, ADC, `gemini-3.6-flash`, `google-genai==2.34.0` in isolated `.venv`. No API keys, credential-file reads or dotenv defaults. Requested max_output_tokens8192, LOW thinking, temperature0, structured JSON/schema, one candidate, no tools/continuation, SDK attempts1, HTTP300000ms and hard process300s. Temperature0 does not imply reproducibility; the model docs say custom temperatures are ignored. Raw request/response, usage, hashes, returned model and exact execution settings are saved locally.

The **$15 ledger ceiling is NOT a provider billing cap**. Before every generation, CountTokens includes instructions/schema (an explicit counting-only supplement conservatively covers config/schema omissions); that operation is separately recorded and documented free. Reserve counted input+1024, plus twice the documented65536 model output maximum, at $1.50/M input and $7.50/M candidates+thinking, round up cents and at least$1. Twice the maximum is an owner-approved estimate, not a documented combined maximum. Atomic SQLite transactions include all accounted spend and outstanding reservations. Unknown usage retains the reservation; a true overrun is recorded, never truncated. Each retry needs another reservation; this probe has no retries. Subsequent stage limits remain at most2 concurrency and2 retries, but continuation is currently stopped. Deadline November17,18:00 America/Los_Angeles. No trial balance or billing protection is assumed.

Fresh metadata reservation remains commit6e085a5:36 release groups across9 issuers, no bodies, labels or inference. Diagnostic examples are consumed data, never held out. The unchanged gold is source-curated/agent-reviewed, not owner-verified. The [owner packet](owner_review_packet.md) keeps the same four seeded random cases plus three fixed high-risk cases,88min estimated/120min maximum. Only the Agilent addendum has model output; all other outputs remain not run. Human review is pending; a sample review does not validate every label.

Every candidate remains quarantined. Exact quote membership is not semantic validation. Fiscal/Decimal/source checks rejected both current proposals; no production guidance, forecast probabilities, or live-lock inputs changed. Prior failed v1/v2 artifacts remain intact. Cache keys use input hash+explicit model+prompt version, with provider/execution checks. No fresh evaluation, promotion, expansion, Session6, website work or training is authorized.

Read-only local checks (no Vertex calls):

```sh
.venv/bin/python -m earnings.hybrid.runner status
.venv/bin/python -m pytest tests/earnings/test_hybrid.py -q
```

Do not use `probe` or `run` after this stop without resolving the recorded gate with the owner. The status command reports `PROBE_USAGE_UNRESOLVED_STOP_REVIEW_REQUIRED`. No new inference may be inferred from remaining budget. Pin setup with existing root requirements and `earnings/hybrid/requirements.txt`; do not change the shared deals environment. Raw requests/results/cost SQLite stay ignored under `data/cache/earnings/hybrid_diagnostic_vertex_v1/`; committed summaries include hashes and original usage counters.

`session3-lock-ready` still resolves to94984fc3ce33c6e85a287738d3a617561cd0cefc. Fixed-input/time regression and PostgreSQL READ ONLY dry runs must be repeated before stopping. Separate manual eligibility openings remain OKTA November16,21:00Pacific; CRM November17,21:00Pacific; IOT/S November18,21:00Pacific. They are not scheduled jobs or authorized locks. Refresh publication evidence and use actual time under the existing prediction workflow. Visual compatibility remains unverified before merging. No merge/push/deployment.
