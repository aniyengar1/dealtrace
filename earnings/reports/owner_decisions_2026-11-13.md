# November13 owner decisions — preparation and completed diagnostics

Recorded after completion on November14 UTC / November13 America/Los_Angeles. No live predictions exist. No future lock was scheduled or executed. The manual-guidance workflow remains separate from quarantined extraction candidates.

## Manual prediction priority and checkpoints

Original `quarter-frequency-v1` is unchanged: eligible class count/N, original historical selection and pooling, Decimal first-two half-even24-place rates plus exact above residual. New **`quarter-frequency-laplace-v1`** uses `(class count+1)/(N+3)`, fixed Dirichlet(1,1,1), no fitting or future-outcome tuning. It calls the same selector, including the six-own-quarter threshold and documented >=12-observation/two-company pooled fallback. All ten currently use own history. This is not calibrated or a claim of improved predictive quality.

[Readiness table](two_method_readiness_2026-11-13.md) contains all ten sample counts and both probability vectors. [Exact preparation probabilities and historical IDs](../validation/two_method_preparation_probabilities.json) store unambiguous normalized Decimals. Preparations are not prospective predictions. Current eligible counts: ADBE8(0/0/8), CRM8(0/4/4), CRWD7(0/0/7), GTLB7(0/0/7), IOT8(0/0/8), LULU8(2/0/6), MDB7(0/0/7), OKTA7(0/0/7), PD7(0/3/4), S8(0/1/7). Order is below/within/above.

Both methods select one common guidance version, evidence, historical IDs and probability cutoff per company and insert atomically. Creation timestamps remain individually database-generated; unique keys include method. A partial existing pair blocks instead of silently selecting new later inputs. Migration0104 reproduces Laplace probabilities in SQL;0103 remains intact. Migration0105 preserves owner-source retrieval freshness independently of local file integrity. Brier scoring remains exact-version, append-only and method-agnostic.

**Final prepared checkpoint:** `session3-two-method-lock-ready-20261113-r2` → **`7dc952c635446bb4ed3a6717d58cb7dc003f62cb`**. This is agent-tested and owner-authorized, pending actual owner review. The earlier preparation tag at87f48d4 is preserved; r2 corrects its overly permissive local-integrity source-refresh substitution. Original `session3-lock-ready` remains94984fc3ce33c6e85a287738d3a617561cd0cefc. No tag was moved. Checkpoint dependencies are pinned in `earnings/lock_ready/two_method_requirements.lock`; only pypdf7.0.1 was added to isolated `.venv`. Code was frozen before November16,21:00Pacific; the actual tag creation time is in [checkpoint metadata](../lock_ready/two_method_checkpoint.json).

### Owner-provided evidence intake

CRWD and MDB PDFs, exact original announcement URLs and owner-reported retrieval times are **outstanding**. Expected December1 after-close announcements remain leads and were not promoted. [Intake instructions](../OWNER_EVIDENCE.md) preserve original bytes/SHA256, supplier, URL, owner-reported retrieval, actual ingestion and separate document-review provenance. Full identity, fiscal period, dateline and explicit results-publication checks precede optional append. Approved versions are user_verified, never independently HTTP-verified by Codex. Failed/403 records remain unchanged; file integrity does not establish authenticity.

Mandatory source rules are explicit:

1. Independent HTTP evidence still requires a fresh full-document check and unchanged reviewed hash.
2. Owner-file evidence uses preserved file/review verification without the blocked announcement download. **Source retrieval must still be within ten minutes at lock time**. Local hashing has a separate current timestamp and cannot freshen owner retrieval. Both application and DB enforce this. Files supplied now may need a new genuine owner retrieval/review version when locking, or a separately approved freshness-policy change; no timestamps are invented.
3. Both routes still need the separate fresh SEC + observable official-IR already-public-results check (two-minute DB freshness). An inaccessible news inventory may still block a company even after its announcement PDF qualifies. No absence of results is inferred from403/empty pages.

### Exact future manual command

After intake/review, source refresh and resolution of all actual-time checks, use a new output filename:

```sh
.venv/bin/python -m earnings ingest ALL --refresh
.venv/bin/python -m earnings load-guidance ALL
.venv/bin/python -m earnings.predict --lock --methods both --output data/cache/earnings/lock-runs/two-methods-manual-unique.json
```

Okta opens **November16,21:00Pacific**, strict deadline December1,00:00America/New_York. Salesforce opens November17,21:00Pacific; Samsara/SentinelOne November18,21:00Pacific. CRWD/MDB openings remain unverified pending files; PD/GTLB/ADBE/LULU still lack qualifying results-publication evidence. Adobe's call listing is insufficient. Date/after-close evidence uses start-of-release-date, never16:00 or call time. No wait loop, scheduler or automatic lock exists.

## Completed ten-release diagnostic

Ten revised release requests completed with **one inference attempt each, no retries**, sequential concurrency1(maximum allowed2). Every result returned requested `gemini-3.6-flash`, STOP. Project `just-rhythm-506202-j8`, global, Vertex ADC, SDK2.34.0, LOW thinking, max_output_tokens8192, structured JSON, temperature0 requested,300-second hard timeout. Effective perfect determinism is not claimed. No substitution was requested or indicated; no storage/batch jobs, credential-file display or deals-run access occurred.

The revised Agilent call ran first; the remaining nine reused its successful cached response rather than calling it again. The nine-call execution ran **2026-11-14T03:22:22.212503Z–03:24:37.489417Z**, before the November17,18:00Pacific deadline. All complete requests were counted before generation. A separate new prompt/configuration version `hybrid-diagnostic-v4-compact-owner-reservation` was frozen before inference. Full canonical releases plus compact table matrices/header positions/spans retained all relevant text and footnotes. Agilent prompt tokens fell from89,449 to46,309, an observed combined context/schema/prompt reduction, not an isolated causal tokenizer experiment. New pre-count46,870 remained conservative. Original and revised raw inputs/outputs/validation/configuration records are preserved separately.

### Candidate results and limitations

There are **26 observations:21 current-release observations plus5 prior-context observations**. All21 current observations are rejected and quarantined. Three are intentionally noneligible outputs(two constant-currency observations at ZM and one implied-quarter observation at IOT); they are not accepted reported-revenue guidance. The remaining18 direct reported proposals are blocked by evidence/status checks. Accepted0; flagged-only/deterministic-pass0; all rejected records still require review. No model candidate reached production or live-lock inputs.

Sixteen source-curated reference targets are in scope: fourteen from eight exhaustively reviewed pilot releases, plus two positive-only quarter targets at IOT/CRWD. Two additional annual proposals at those positive-only releases remain unjudged by that gold scope. **All16 reference numeric ranges have corresponding proposed metric/end/currency/range values**, so there are0 numerical-range identification omissions under that narrow criterion. This is not source validation, complete-period validation, basis comparability, status agreement or acceptance. All16 remain unaccepted: accepted-output strict recall0/16, precision undefined(no accepted outputs). No hybrid quality gate or generalization claim is passed.

|Company|Reference targets|Current rejected|Intentional noneligible subset|Reference ranges not proposed|Observed blocking codes|
|---|---:|---:|---:|---:|---|
|A|2|2|0|0|INVALID_STATUS_REFERENCE_INPUT, UNRESOLVED_STATUS|
|ADI|1|1|0|0|CALENDAR_BOUNDARY_MISMATCH, UNRESOLVED_STATUS|
|AMAT|1|1|0|0|CURRENCY_NOT_SUPPORTED, NUMBER_NOT_IN_AMOUNT_EVIDENCE, UNRESOLVED_STATUS|
|DOCU|2|2|0|0|INCOMPLETE_EVIDENCE_ROLES, MISSING_COLUMN_IDENTITY, MISSING_EXACT_MATCH, MISSING_MATCHING_TABLE_HEADER, REPEATED_EXACT_MATCH, SCALE_NOT_SUPPORTED, UNRESOLVED_STATUS|
|FIVE|2|2|0|0|UNRESOLVED_STATUS|
|HIMS|2|2|0|0|INCOMPARABLE_STATUS_REFERENCE, INVALID_STATUS_REFERENCE_INPUT, REPEATED_EXACT_MATCH, UNRESOLVED_STATUS|
|TDOC|2|2|0|0|INCOMPARABLE_STATUS_REFERENCE, INCOMPLETE_EVIDENCE_ROLES, INVALID_STATUS_REFERENCE_INPUT, MISSING_MATCHING_TABLE_HEADER, MISSING_STATUS_EVIDENCE, NUMBER_NOT_IN_AMOUNT_EVIDENCE, REPEATED_EXACT_MATCH, UNRESOLVED_STATUS|
|ZM|2|4|2|0|NONELIGIBLE_OR_AMBIGUOUS_INTERPRETATION, UNRESOLVED_STATUS|
|IOT|1|3|1|0|INCOMPLETE_EVIDENCE_ROLES, NONELIGIBLE_OR_AMBIGUOUS_INTERPRETATION, REPEATED_EXACT_MATCH, UNRESOLVED_STATUS|
|CRWD|1|2|0|0|INCOMPLETE_EVIDENCE_ROLES, REPEATED_EXACT_MATCH, UNRESOLVED_STATUS|

Key distinctions:

- Status:18 current proposals explicitly abstained with unresolved status. Three other revision claims were blocked on prior-reference input/basis issues. The model did not invent initial status to satisfy gold labels. Some source-curated status labels use prior history not established by the supplied context. Conservative abstention is not an amount hallucination, and it still fails strict acceptance.
- Quote locations: complete exact strings resolve deterministically. Short repeated labels/passages remain blocked; no occurrence is silently selected. DOCU also supplied a newline-bearing passage not equal to pinned canonical text. Repeated/absent evidence cannot approve semantic roles.
- Tables: DOCU/TDOC missed applicable column/header evidence. AMAT cited `6,700` but proposed the literal`6700`, and omitted currency-symbol evidence. Decimal economic amounts can agree while literal/source requirements still fail.
- Fiscal period: ADI supplied only a correct-looking end date while leaving start null; the current validator blocks partial boundary pairs instead of filling one. This is a conservative validator-contract limitation, not evidence that the supplied end date is wrong.
- Scope: HIMS/TDOC current/prior acquisition/tariff qualifiers were not established as compatible. No normalization was invented. ZM constant-currency and IOT implied guidance were explicitly excluded.

[Final field-level diagnostic analysis](../validation/hybrid_v4_diagnostic_final_analysis.json) includes every proposal, exact evidence, locations, reference IDs and field differences. It is consumed diagnostic data, not fresh or human-reviewed performance. The intermediate analysis is retained; its noneligible-subset count was corrected from1 to3 by recognizing CC outputs, without changing prompts, model responses, validation or acceptance. Frozen v1/v2 failed evaluations remain untouched. No post-result rule/prompt tuning or extra calls occurred.

## Cost and usage accounting

Owner-approved estimate for each revised call: `counted_input*1.50/M + (8192*2)*7.50/M`, with no old model-maximum/$1-floor reservation substituted. Reservations were atomic against accounted spend plus all outstanding holds <=$15, including the original$1.12. This is **not a documented combined output/thinking bound or guaranteed provider billing cap**. Pricing was rechecked on the [official page](https://cloud.google.com/model-garden/pricing); approved upper rates were used without assumed discounts/trial balances. These are internal usage-based accounting costs, not settled Google invoices.

|Release|Pre-count input|Prompt/candidate/thinking counters|Reservation USD|Accounted USD|Known subtotal USD (not extra charge)|
|---|---:|---|---:|---:|---:|
|pilot-0|46870|46309/2595/2086|0.193185|0.104571|0.104571|
|pilot-1|38091|37530/777/1113|0.1800165|0.07047|0.07047|
|pilot-4|52036|51475/1033/absent|0.200934|unresolved|0.08496|
|pilot-11|40874|40313/1341/absent|0.184191|unresolved|0.070527|
|pilot-14|24712|24151/1305/absent|0.159948|unresolved|0.046014|
|pilot-19|57215|56654/2203/absent|0.2087025|unresolved|0.1015035|
|pilot-27|63417|62856/1862/1320|0.2180055|0.118149|0.118149|
|pilot-28|31494|30933/2111/absent|0.170121|unresolved|0.062232|
|IOT-0001642896-24-000059|32036|31475/2170/913|0.170934|0.070335|0.070335|
|CRWD-0001535527-24-000017|47078|46517/1647/absent|0.193497|unresolved|0.082128|

Four revised attempts have complete usable counters: **$0.363525 accounted**. Six revised attempts have missing thinking fields and retain **$1.1173935** of reservations. The new original-body capture proves those six thinking counters were **absent**, not explicitly null; it does not recover the original probe's lost wire representation. The original attempt still holds **$1.12**, unchanged. Total unresolved reservations **$2.2373935**; accounted plus holds **$2.6009185**. No active calls, known accounted/subtotal overrun or control halt occurred; unresolved provider costs remain unknown. Remaining ledger capacity is not authorization for more calls.

Reported-counter subtotals across all11 attempts total **$0.9593205**; this includes the accounted amounts and known portions of unresolved attempts. The unresolved-attempt known subtotal is **$0.5957955**, including original probe$0.148431. It is **not added again** to reservations or counted as a separate charge. Missing thinking is not coerced to zero or inferred by subtraction. CountTokens is separately logged as documented free. [Per-attempt counters, wire field presence and cost evidence](../validation/hybrid_v4_cost_and_usage.json). Raw responses and ledger snapshots stay in the ignored earnings-only cache.

## Owner review packet

[Updated packet](../hybrid/owner_review_packet_v4.md), [selection/provenance manifest](../hybrid/owner_review_manifest_v4.json). The original four seeded random cases and three high-risk cases are unchanged; FIVE/TDOC/ZM were added as supplemental diagnostic coverage. No unfavorable case was removed or replaced. Ten complete release groups are covered, with full source links/pinned text, relevant context, proposed interpretations, exact evidence checks, curated reference labels and blank owner decisions.

Planning estimate **88minutes**: instructions8 + four random×7 + three high-risk×10 + three supplemental×5 + summary7. Up to32min buffer, hard stop120min; unfinished cases remain unreviewed. The packet contains about7,110 words plus linked full sources. It was prepared before Sunday November15. Human review is **0cases/pending**. Source curation and agent/code comparison are not human review; a sample decision cannot validate every label.

## Validation, preservation and stop

**498 passed,3 skipped,2 original expected failures**. No expected failure was removed or counted as repaired behavior. Tests cover original/smoothed math and pooling, no-look-ahead selection, zero counts/all-above, per-method duplicates, DB forged-probability rejection, stale owner evidence, PDF provenance/append behavior, one-attempt atomic reservations, unknown usage, overruns, no double-counting, quarantine invariants and all counter-presence cases.

Original-method fixed-input/time regressions match original tag exactly, and final paired-method regression matches isolated r2-tag code exactly. [Original HEAD](../validation/owner_freshness_r2_original_head.json), [original tag](../validation/owner_freshness_r2_original_tag.json), [paired HEAD](../validation/owner_freshness_r2_pair.json), [paired r2 tag](../validation/two_method_r2_tag_pair_final.json). Eligibility, guidance/history IDs, probabilities and rejection reasons are unchanged for the empirical method.

[Final read-only dry run](../validation/owner_freshness_r2_read_only.json) began2026-11-14T03:41:16.967562Z, PostgreSQL READ ONLY, schema compatible, history ingestion and insertion disabled, ledger0before/0after. Original live source files changed only where explicitly authorized(predict/live); baseline module, manual guidance/history and failed extractor artifacts remain intact. [Protection evidence](../validation/owner_decisions_final_protection.json) records original probe row/events/response preservation and checkpoint hashes. The original$1.12 row was not modified; new attempts/events only appended. Credentials and raw data were not committed.

No fresh release body/inference, production promotion, expansion, Session6, website changes, merge, push or deployment. Visual compatibility remains unverified before a future merge. Stop for owner review; no remaining diagnostic calls, future lock jobs or continuous waiting processes exist.

Formatting check: the only retained `git diff --check` warning is one extra EOF blank line in the frozen `earnings/hybrid/context.py`. Its exact bytes are retained to preserve the executed v4 fingerprint/cache provenance; no financial or runtime behavior is affected. Other staged whitespace checks are clean.
