# Hybrid diagnostic probe — stopped for usage review

Inference was explicitly authorized under the owner's updated concurrent-run authorization. One existing diagnostic Agilent release was processed. The requested model was accessible and returned structured JSON, but **the usage gate failed: `thoughts_token_count` was null**. No retry or further inference was dispatched. Nine approved diagnostic releases remain unrun. No fresh evaluation or production promotion occurred.

## Execution and billing evidence

|Field|Recorded value|
|---|---|
|Stage|Consumed diagnostic only; not fresh evaluation|
|Source|Agilent accession `0001090872-25-000013`, filed May28,2025; exact SEC URL in the evidence JSON and owner packet|
|Provider/auth|Google Vertex AI/Agent Platform, `vertexai=True`, normal ADC; no credential-file or `.env` reads|
|Project/location|`just-rhythm-506202-j8` / `global`|
|SDK|`google-genai==2.34.0`, existing isolated `.venv`; no dependency changes|
|Requested / returned model|`gemini-3.6-flash` / `gemini-3.6-flash` (no more granular identifier returned)|
|Prompt version|`hybrid-diagnostic-v2-owner-estimate`, frozen before inference|
|Generation|Structured JSON/schema; max_output_tokens8192; LOW thinking; temperature0; one candidate; no tools or continuation|
|Timeout/retries|300000ms SDK timeout and300-second hard worker timeout; SDK attempts1; probe one attempt, no retry|
|Probe run|2026-11-13T20:34:38.094031+00:00 through20:34:46.771918+00:00|
|Attempt created|2026-11-13T20:34:39.366553+00:00, ID `bb7bb97b-f98d-497c-847f-012086b915af`|
|Inference latency / finish|7.163454791996628seconds / STOP|
|CountTokens|One request,89940tokens; full payload/instructions/schema plus counting-only schema/settings supplement; documented charge$0|
|Generation counters|Prompt89449; candidates1901; **thoughts null**; total91350; cached input null; tool-use null|
|Reserved before generation|$1.12, retained in full|
|Known-counter subtotal|$0.148431 at accounting rates, **not final actual cost**|
|Final accounted cost|Unknown; no assumption that missing thoughts means zero|
|Ledger totals|One attempt, no active calls; known-final-accounted$0; unresolved reservation$1.12; total held$1.12 of$15|
|Stop reason|`SUCCESS_RESPONSE_USAGE_UNKNOWN_OR_INCONSISTENT_STOP`|

Total minus prompt and candidates equals zero, but the experiment requires an interpretable explicit thinking counter. We did not silently manufacture it or treat the request as free. The subtotal above includes only reported prompt/candidate tokens; invoice cost was not queried. Raw counters, response, CountTokens result, full execution request and append-only local ledger events are preserved under ignored `data/cache/earnings/hybrid_diagnostic_vertex_v1/`. The committed [evidence summary](../validation/hybrid_authorized_probe_evidence.json) includes the raw-response hash. No further inference should occur pending owner review of this usage gap.

**The $15 operational ledger ceiling is NOT a provider billing cap.** The reservation used(89940+1024)input tokens and2×the model's documented65536 output maximum, at$1.50/M input and$7.50/M candidates+thinking, rounded up cents to$1.12 and subject to a$1 minimum. The doubled allowance is the owner's conservative estimate, not a documented combined maximum. Prior experiment charges/reservations were zero. Unknown usage retains the entire reservation; retries need separate atomic reservations. No trial credit balance, current billing protection or introductory discount was assumed. Billing settings were not changed.

[Official pricing](https://cloud.google.com/model-garden/pricing) was checked2026-11-13T20:30:07.503209+00:00; configured upper rates did not exceed approved accounting rates. [Official CountTokens documentation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/capabilities/get-token-count) states it has no charge. The [response reference](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/rest/v1/GenerateContentResponse) exposes candidate and thinking counters separately. Observing this probe does not establish a universal token/billing bound. Temperature0 is requested, not a perfect-determinism guarantee.

## Diagnostic extraction results

Offline analysis reused the preserved response without another model call. Four observations were proposed: two current targets and two prior-context records. All four failed deterministic evidence checks and remain quarantined. No accepted candidate was produced.

|Current proposal|Normalized USD range|Result|
|---|---:|---|
|FY2025 annual revenue, raised|6,730,000,000–6,810,000,000|Rejected: `QUOTE_OFFSET_MISMATCH`, `INCOMPLETE_EVIDENCE_ROLES`, `INVALID_STATUS_REFERENCE_INPUT`|
|Q3 FY2025 revenue, initial|1,645,000,000–1,675,000,000|Rejected: `QUOTE_OFFSET_MISMATCH`, `INCOMPLETE_EVIDENCE_ROLES`|

Correction from offline review: all four model-proposed quote strings are present verbatim in the pinned sources, including “Q3 revenue outlook is expected…” in the opening summary. The supplied character offsets are wrong. The annual quote strings each occur twice; the quarterly strings each occur once. The original validator rejected the supplied quote/offset pairs, not quote membership. See `hybrid_offline_correction_2026-11-13.md` for the distinct revalidation result; the original failed outputs and score remain preserved. Both current proposals lacked the distinct evidence roles establishing scope, period, units, basis, guidance type and issuance. The annual revision's prior reference also failed deterministic validation. This is evidence failure even where proposed amounts match curated labels. Exact matching alone would still not prove semantic correctness.

The [offline score](../validation/hybrid_authorized_probe_score.json) reports0true positives,0accepted predictions,2gold targets,2misses: strict recall0%, precision undefined(no accepted predictions). Two current proposals are validation-rejected abstentions. These are pipeline scores for **one consumed diagnostic release**, not held-out quality or evidence of generalization. No scores are attributed to the nine unrun releases; they are not counted as misses. No prompt, rule, schema or validation tuning followed these results. Frozen v2 and its failed evaluations remain intact.

## Fresh reservation and owner review

Fresh selection remains commit `6e085a5`:36metadata-only groups across9issuers, all unexamined bodies and related versions embargoed. No fresh source bodies were opened, labeled or inferred. The CFLT metadata gap remains documented.

The [owner review packet](../hybrid/owner_review_packet.md) retains the exact seeded four-case random sample plus three fixed high-risk cases:7cases,88minutes estimated,120minutes hard maximum. The existing Agilent case includes a clearly labeled unverified-model addendum, not an extra case. Only one case has hybrid output; other cases can be reviewed as source-curated examples but have no model results. Labels are source-curated/agent-reviewed; **actual human review is0cases and remains pending**. The owner is the only human reviewer; reviewing this sample will not verify every label.

## Verification and protected workflow

- Full suite: **449passed,3skipped,2xfailed**. The two existing v1 expected failures remain unresolved and are not counted as repairs. New tests cover provider counting serialization, operational reservations, probe/no-retry gates, attempt cost stops and the exact missing-thinking-counter failure with retained$1.12.
- Fixed-input/time regression: HEAD and isolated reviewed checkpoint outputs are identical across all seven scenarios, including eligibility, selected guidance/history IDs, probabilities and rejection reasons. [HEAD](../validation/hybrid_authorized_head_regression.json), [checkpoint](../validation/hybrid_authorized_tag_regression.json).
- Actual-clock dry runs: HEAD2026-11-13T20:38:19.288562+00:00 through20:38:19.301451+00:00; checkpoint separately recorded. PostgreSQL `transaction_read_only=on`, schema compatible, history ingestion suppressed, insert adapter disabled, ledger count0before/0after. No predictions created. [HEAD](../validation/hybrid_authorized_head_dry_run.json), [checkpoint](../validation/hybrid_authorized_tag_dry_run.json).
- [Protection evidence](../validation/hybrid_authorized_protection.json):84tracked protected files match prior hashes; no prediction code/data/schema or frozen extractor artifacts changed. Root dependencies unchanged. `session3-lock-ready` remains annotated tag object `4fa9ec0f58e1e8c4701c6d6ea52f04653a969385`, resolving to commit `94984fc3ce33c6e85a287738d3a617561cd0cefc`; neither moved nor overwritten.
- `runner status` is local only and now reports `PROBE_USAGE_UNRESOLVED_STOP_REVIEW_REQUIRED`. Failed probe cache cannot be interpreted as permission to dispatch remaining cases. No inference was made to test this stop.

## Manual prediction workflow and stop

The unchanged Okta opening remains **November16,21:00America/Los_Angeles**(November17,05:00UTC), with conservative deadline December1,05:00UTC based on a date-only/after-close release. The dry run correctly reports `OUTSIDE_14_DAY_WINDOW`. Other manual openings remain Salesforce November17,21:00Pacific and Samsara/SentinelOne November18,21:00Pacific. These are openings, not scheduled jobs. Refresh results-publication evidence and already-public checks with actual current time using the reviewed workflow before any separately authorized lock. This experiment authorizes no live locks and does not satisfy the prospective gate.

The diagnostic stage stopped before the November17,18:00Pacific deadline. Remaining work is owner review of the missing usage field, the quarantined evidence failures and the bounded packet. Nine diagnostic calls remain unperformed; no automatic retry or fresh evaluation is planned. No production promotion, website changes, broader expansion, Session6, training, merge, push or deployment. Visual compatibility remains explicitly unverified before any future merge.
