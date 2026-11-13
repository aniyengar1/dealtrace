# Offline hybrid correction — no new inference

This pass changes deterministic evidence handling, the proposed evidence contract and future response metadata capture. **No Vertex inference, CountTokens request, retry or access probe occurred.** All extraction results below reuse the single saved Agilent probe. They are not fresh model performance, a new successful extraction, or human validation. Fresh releases remain untouched; all candidates remain quarantined.

## Correction to the prior report

All four proposed quote strings occur verbatim in the pinned canonical sources. The model supplied incorrect offsets. The prior report incorrectly described the Q3 quote as non-verbatim because it compared a different occurrence/section. That report now explicitly corrects this statement. Its original version is preserved at `earnings/hybrid/archive/probe_v2/original_probe_report.md`; original failed outputs and scores are unchanged.

|Candidate|Proposed source/period, USD range, status|Model offsets|Exact source match(es)|Cached v3 disposition|
|---|---|---|---|---|
|0|Current FY2025 annual; $6.73–6.81B; raised referencing candidate 2|[507,580)|[649,728), [3101,3180)|Repeated; no location selected. Incomplete roles, missing status evidence, invalid prior-reference input. Status unresolved.|
|1|Current Q3 FY2025; $1.645–1.675B; initial/first observed|[709,787)|[885,970)|Unique location proposed. Incomplete roles; missing status evidence; initial not established. Status unresolved.|
|2|Prior FY2025 annual; $6.68–6.76B; initial/explicit issuance claimed|[506,579)|[673,752), [3183,3262)|Repeated; no location selected. Incomplete roles and missing status evidence. Status unresolved.|
|3|Prior Q2 FY2025; $1.61–1.65B; initial/first observed|[703,778)|[904,987)|Unique location proposed. Incomplete roles; missing status evidence; initial not established. Status unresolved.|

Each original proposal claimed consolidated revenue, reported basis, USD and direct range guidance. Issuance was May 28, 2025 for current records and February 26, 2025 for prior context. Physical period boundaries were null in the model output; the registered calendar resolved annual November 1, 2024–October 31, 2025, Q3 May 1–July 31, 2025 and Q2 February 1–April 30, 2025. These calendar resolutions are code-derived, not newly quoted model evidence.

Exact proposed passages:

- Current annual: “Full-year revenue outlook is now in the range of $6.73 billion to $6.81 billion”
- Current quarter: “Q3 revenue outlook is expected to be in the range of $1.645 billion to $1.675 billion”
- Prior annual: “Full-year revenue outlook is now in the range of $6.68 billion to $6.76 billion”
- Prior quarter: “Q2 revenue outlook is expected to be in the range of $1.61 billion to $1.65 billion”

Sources: [May 28 Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1090872/000109087225000013/exhibit991-q225pressrelease.htm), accession `0001090872-25-000013`; [February 26 Exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1090872/000109087225000003/exhibit991-q125pressrelease.htm), accession `0001090872-25-000003`. The saved request contains exactly the same canonical documents as the pinned input.

The wrong offsets are model-output errors, not a discovered tokenizer, Unicode or canonicalization defect. Each supplied end-minus-start also differs from its quote's character length. Decimal normalization remains correct. Every original proposal supplied only an amount role. Neither successful quote location nor matching amounts establishes scope, period, issuance, basis or revision semantics. Annual numeric/currency/scale evidence errors in v3 are secondary consequences of rejecting ambiguous locations, not new claims that the financial normalization is wrong.

## Deterministic evidence contract

`evidence.py` searches only the named pinned canonical source, with no whitespace rewriting, fuzzy matching, outside knowledge or source replacement. It preserves the model quote and original offsets. It records **all** exact locations and returns a resolved location only when there is exactly one match. Repeated or missing quotes block even when a model offset points at one occurrence. It never silently chooses a match.

The v3 schema permits a `roles` array on one passage; legacy single-role proposals remain readable. New prompts request quotes with null offsets. One sufficient passage may support multiple roles without artificial duplicate quotations. Candidates require metric, scope, period, units, basis, guidance type, amount and issuance evidence; every claimed status also needs status evidence. First observed is not proof of initial issuance. Unsupported initial/revision claims retain their original proposal but have `resolved_status=unresolved` and remain blocked.

Revision comparison now includes fiscal year and quarter in addition to supplied physical dates, preventing two null date pairs from accidentally making different fiscal targets comparable. Prior-reference errors continue to block revisions. Role assignments and quote membership are still fallible semantic claims: every deterministic-pass candidate requires human review and remains quarantined.

[Cached revalidation](../validation/hybrid_offline_correction_revalidation_v2.json) preserves original artifact hashes and original model proposals. All four observations remain blocked; no new precision/recall or successful extraction is claimed. The earlier local compact-package proposal is retained separately in `hybrid_offline_correction_revalidation.json`; the v2 file only refines that offline packaging proposal, not model outputs.

## Why the prompt was large

The provider reported **89,449 prompt tokens**. Saved pre-call CountTokens reported **89,940**, a conservative difference of 491. The configured additional input reservation margin was 1,024 tokens. CountTokens included the full input/instructions/generation schema plus an explicit counting-only schema/settings supplement. That supplement was **not** sent to generation. The difference cannot be assigned exactly to the supplement: provider counting and schema handling may differ.

Only aggregate token counts were saved. Exact component token attribution is unavailable without another supported tokenization/counting operation, which this offline pass does not perform. The following are measured **JSON bytes, not invented token counts**:

|Component|Current release|Prior context|
|---|---:|---:|
|Full document JSON|141,184|129,770|
|Canonical text value|24,403|23,231|
|All table JSON|116,360|106,114|
|Of tables: duplicated table text values|6,434|5,779|
|Of tables: row/cell objects|103,677|94,104|
|Of tables: duplicated surrounding-context values|5,438|5,438|

Rows beneath “all table JSON” are components, not additional totals. The combined payload is **270,971 bytes** including document metadata and JSON framing. There are nine tables per release. Canonical text contains 24,121 and 22,979 characters respectively. Raw HTML markup was not sent. Repeated cell keys such as text/tag/rowspan/colspan, table representations already present in canonical text and repeated preceding context account for much of the expansion. Cell object JSON alone is 197,781 bytes.

Saved instructions are **3,118 UTF-8 bytes**. Saved Pydantic schema JSON is **4,292 bytes**. A network-denied SDK HTTP mock, using the archived original schema/prompt, reconstructed a **5,345-byte wire schema** and 338,670-byte request body. The wire body escapes the JSON payload inside a text string; those wire escaping bytes are not extra source text tokens. See [mock reconstruction](../validation/hybrid_offline_original_wire_size.json). It is not an original wire capture or a provider count.

### Proposed smaller package — not activated

Retain both **complete canonical releases**, including all outlook sections, datelines, company identity, footnotes, caveats, unrelated metrics and historical evidence. Keep every table's row/column cell text, header-cell positions, table ID, canonical boundaries and nondefault row/column spans. Remove repeated `table.text`, repeated surrounding-context copies, default per-cell attributes and verbose metadata keys. No section or source content is truncated or selected using v2 hits.

This lossless source-content proposal is **109,692 JSON bytes**, down from 270,971 (161,279 bytes removed, approximately 59.5%). It retains table alignment separately from canonical text, using compact span tuples `[row,column,rowspan,colspan]` and header pairs `[row,column]`. Token savings have not been measured and are not asserted. Full prior context remains because status evidence is unresolved; selecting only relevant historical paragraphs would require an independently reviewed section manifest. No active inference preprocessing was switched to this proposal.

## Future response capture and accounting

The original “raw” probe artifact is an SDK model dump; it cannot establish whether the service omitted thinking usage or sent explicit null. This limitation cannot be repaired retroactively.

Future transport uses the supported SDK `HttpOptions.client_args` path for an HTTPX response hook. It reads the response before SDK parsing, hashes the original body and records status, byte length, usage-metadata presence and allowlisted raw usage-counter presence/null/value. It never stores headers, request URLs, cookies, credentials, arbitrary error messages or arbitrary body fields. SDK serialization is explicitly labeled `SDK_MODEL_DUMP_NOT_ORIGINAL_HTTP_BODY`. [SDK configuration documentation](https://googleapis.github.io/python-genai/), [HTTPX response-hook documentation](https://www.python-httpx.org/advanced/event-hooks/).

Network-denied HTTP mocks exercise **absent, explicit null, zero and numeric values for all six usage counters through the real pinned SDK** (24 combinations). Absent and null remain distinguishable in captured metadata even though SDK serialization collapses them to null. Zero and numeric values survive. Tests include synthetic secret-bearing headers/body fields to verify they are not logged. This establishes local transport behavior, not live endpoint behavior.

The original ledger is read-only in this pass: one unresolved attempt, **$1.12 held**, final accounted cost null. The $0.148431 reported-token subtotal remains informational and is not added as a separate charge. The $15 ledger ceiling remains operational, **not a guaranteed provider billing cap**. No missing counter is coerced to zero; no accounting policy changed.

## Proposed next-call configuration and stop

- Same pinned Vertex project/global/ADC, model `gemini-3.6-flash`, SDK 2.34.0; no substitutions or dependency changes.
- Proposed v3 multi-role evidence schema and prompt; deterministic locations and original-body usage metadata capture.
- Proposed complete-text/compact-table package above, subject to approval and preprocessing fingerprint update before any call.
- Keep LOW thinking, max_output_tokens 8,192, temperature 0, structured JSON, one candidate, no tools/continuation, 300-second timeout and SDK attempts 1. These settings have **not** been live-tested with v3.
- Refresh official pricing and perform a separately authorized complete-request count before any future call; preserve the $1.12 reservation. Existing per-attempt/total operational controls remain, including owner-approved doubled documented output allowance as an estimate, not a guarantee.

**Active config is `OFFLINE_CORRECTION_ONLY_NO_NEW_INFERENCE`; preflight blocks new provider operations.** The historical authorization is preserved but does not authorize v3 dispatch. No next call or retry was made or scheduled. Fresh evaluation, production promotion, website work and broader expansion remain blocked.

## Verification and preservation

- Final suite: **479 passed, 3 skipped, 2 existing expected failures**. Network-denied hybrid tests cover unique/repeated/missing quotes, preservation of model offsets, one passage with multiple roles, unsupported initial status, different fiscal-target revisions, complete-text compact packaging, usage counter presence and header/body-field redaction. No expected-failure test was removed or counted as repaired behavior.
- Fixed-input/time prediction regression: HEAD exactly matches the isolated `session3-lock-ready` checkpoint across all seven scenarios, including guidance/history selection, probabilities, eligibility and rejection reasons. [HEAD](../validation/hybrid_offline_head_regression.json), [checkpoint](../validation/hybrid_offline_tag_regression.json).
- Actual-clock dry runs: HEAD began November 13, 2026 at **22:13:31.723812 UTC**, finishing at 22:13:31.737350 UTC. Both HEAD and checkpoint used PostgreSQL READ ONLY with ledger insertion disabled and history ingestion suppressed. Schema compatibility passed; ledger counts remained **0 before / 0 after**; no predictions were created. [HEAD](../validation/hybrid_offline_head_dry_run.json), [checkpoint](../validation/hybrid_offline_tag_dry_run.json).
- [Preservation manifest](../validation/hybrid_offline_correction_protection.json): all **84 protected files** match previous hashes; original probe request/response/result/input/run and SQLite ledger hashes are unchanged. Archived v2 code/config/schema/prompt/freezes match commit `244bf35` byte-for-byte. No dependencies changed. `session3-lock-ready` remains at commit `94984fc3ce33c6e85a287738d3a617561cd0cefc`.
- Okta's manual eligibility opening remains November 16 at 9 p.m. America/Los_Angeles. The unchanged workflow still requires refreshed publication evidence, already-public checks and actual current time. This experiment does not schedule or authorize locks or satisfy the prospective live gate.

Stop for review. No other nine diagnostic releases, fresh releases, website, production guidance, live-lock inputs, merges, pushes or deployments were changed or executed.
