# Offline diagnosis of the saved ten-release diagnostic

This is classification of unchanged saved results, not extractor tuning, revalidation under corrected rules, fresh-set evaluation, rescoring or a successful new extraction. No Vertex/CountTokens/provider requests occurred. No original response, score, candidate, evidence, gold label or cost reservation was changed. Actual human review remains pending.

## Populations and counts

The ten responses contain **26 observations**:

|Population|Count|Relationship|
|---|---:|---|
|Current proposals corresponding to reference numeric ranges|16|14 targets from eight exhaustively source-curated pilot releases;2 positive-only quarterly targets at IOT/CRWD|
|Additional current annual proposals at IOT/CRWD|2|Outside those old positive-only gold scopes; unjudged, not declared correct|
|Intentionally noneligible current observations|3|Two ZM constant-currency ranges; one IOT implied Q4 range. These were explicitly identified as noneligible, not accepted reported guidance|
|Total current observations|21|All rejected/quarantined by the full validation contract|
|Prior-context observations|5|Agilent2, HIMS1, TDOC2; references for history/status, not additional current targets|
|All observations|26|21+5|

“16 reference ranges proposed” used only metric/end/currency/Decimal-range agreement. It does not establish exact quote evidence, full fiscal boundaries, comparable basis, revision status, semantic correctness or acceptance. There are0 numerical-range-identification omissions under that narrow criterion, but **16 unaccepted reference targets** under the full contract. Accepted0; flagged-only passes0. No quality gate is claimed. In particular,21rejections are not21 proven semantic false positives.

## Grouping by failed rule

Counts are **candidate-level, nonexclusive**: one candidate can have several rules. There are58 rule hits across21 current candidates. The [full grouping artifact](../validation/diagnostic_rule_failure_review.json) lists every candidate UUID/company/fiscal label per rule.

|Failed rule|Candidates|Diagnosis|
|---|---:|---|
|UNRESOLVED_STATUS|18|Explicit abstention about guidance history; also a design choice making unknown status reject an otherwise identifiable range|
|REPEATED_EXACT_MATCH|10|Source-location ambiguity; short labels/passages occur more than once; not proof of a false quote|
|INCOMPLETE_EVIDENCE_ROLES|9|Missing **or unusable** evidence roles; often cascades when repeated/missing passages cannot supply their claimed roles|
|MISSING_MATCHING_TABLE_HEADER|4|Missing/unusable header evidence plus an overly restrictive inside-table-only representation|
|INVALID_STATUS_REFERENCE_INPUT|3|Dependency propagation; Agilent is blocked solely because its prior range's own status is unknown; HIMS/TDOC also have other issues|
|NONELIGIBLE_OR_AMBIGUOUS_INTERPRETATION|3|Correct exclusion of the two CC and one implied observations; not three accepted semantic errors|
|INCOMPARABLE_STATUS_REFERENCE|2|HIMS/TDOC qualifier/basis uncertainty; exact qualifier tuples differ and comparability is not established|
|NUMBER_NOT_IN_AMOUNT_EVIDENCE|2|AMAT/TDOC normalized digit strings omit source thousands commas; raw-literal contract mismatch, not a wrong computed dollar amount|
|MISSING_COLUMN_IDENTITY|2|DOCU did not supply complete column identity; genuine missing table association evidence|
|CALENDAR_BOUNDARY_MISMATCH|1|ADI partial-boundary handling defect/limitation; supplied end agrees with registered calendar but missing start causes rejection|
|CURRENCY_NOT_SUPPORTED|1|AMAT lacks the needed currency-symbol evidence in its usable cited passages|
|MISSING_EXACT_MATCH|1|DOCU cited a newline-bearing passage absent from the pinned canonical text; not just a wrong offset|
|SCALE_NOT_SUPPORTED|1|DOCU scale support became unavailable when its heading passage failed exact location|
|MISSING_STATUS_EVIDENCE|1|TDOC annual reaffirmation lacked usable status-role evidence; equal amounts alone do not settle basis/reaffirmation semantics|

These counts are not additive semantic-error counts. For example, a missing heading can produce missing roles, missing header and unsupported scale simultaneously.

## Semantic risk versus other failure classes

### Genuine eligibility exclusions and unresolved semantics

ZM's two CC ranges and IOT's implied Q4 are **correctly excluded** under the agreed target definition. The model explicitly categorized these negatives; emitting them as labeled noneligible context is not equivalent to promoting them as consolidated reported direct guidance.

HIMS's current/prior annual ranges carry different assumptions: the prior observation additionally assumes ongoing compounded-semaglutide access/unchanged business relationships. TDOC's prior/current qualifiers refer to Catapult/purchase-accounting exclusions versus UpLift/tariff assumptions. The current code compares exact qualifier tuples. A difference is a reason for review, not automatic proof that revenue bases are incompatible; an omitted qualifier is not proof that the assumption ended. Conversely, equal numerical ranges do not establish comparability. Neither example should be silently normalized or accepted.

No confirmed wrong dollar range is demonstrated by the16 narrow reference matches. That does **not** prove all21 interpretations are semantically correct. Metric scope, directly issued versus implied guidance, period linkage, currency, acquisition assumptions and claimed revision history remain fallible and require evidence/human review. Gold labels are source-curated/agent-reviewed, not completed owner adjudications.

### Missing evidence and source-location ambiguity

DOCU cites:

`Guidance\nThe company currently expects the following guidance:\n▪ Quarter ending April 30, 2025 (in millions, except percentages):`

That exact string is absent from the single-space canonical source. Its `Total revenue [1]` label also repeats. The proposed quarter values745–749million align numerically with the reference, but that does not supply a valid located heading/column relationship. No fuzzy whitespace replacement or first-occurrence choice was performed.

IOT/CRWD cite repeated outlook rows/labels, and HIMS cites an acquisition-exclusion sentence appearing multiple times. The locator correctly lists all matches and leaves resolution null. They need longer unique evidence or an explicit validated table/section association, not weaker quote matching.

Table headings can legitimately sit outside an HTML table. The validator currently requires a table-header quote to occur inside `table.text`. Some saved outputs also genuinely omit column/header roles. This mixture must not be described as four proven model semantic errors. A structural association between the applicable outside heading and exact table would be needed before accepting that evidence.

### Schema/validator design problems

**Agilent status dependency:** the current annual$6.73–6.81B proposal references a prior$6.68–6.76B annual range on the same fiscal period/basis. The prior record's only failure is `UNRESOLVED_STATUS` about its own historical revision. All other prior evidence checks passed. The current annual candidate's sole failure is then `INVALID_STATUS_REFERENCE_INPUT`. Not knowing whether the prior range was itself initial/raised/reaffirmed should not, by itself, invalidate that range as a comparator. This is an over-coupled dependency rule, not evidence of an incorrect current amount or arithmetic.

**ADI partial calendar:** the model supplies end2024-11-02 and startnull. The registered calendar has the same end, yet code rejects because it accepts either both boundaries missing(then fills both) or both exactly matching. Supplying one correct boundary therefore performs worse than supplying neither. `CALENDAR_BOUNDARY_MISMATCH` is misleading here; no contradictory supplied end was found. Any future fix must use only the registered fiscal calendar and still reject conflicting bounds—never assume calendar quarters or normalize fiscal weeks.

**AMAT/TDOC numeric literals:** AMAT supplies value`6700` while its exact amount quote is`6,700`; TDOC supplies`2468`/`2576` while evidence uses`2,468`/`2,576`. Decimal economic normalization is correct, but the prompt asks for raw literals while a schema field named`value` can invite normalized values. The strict raw-string check rejects that mismatch. This is an extraction-contract/schema ambiguity plus a formatting-contract error, not proof of an economic amount error. AMAT still lacks currency evidence; fixing comma handling alone would not validate it.

**Unknown status versus base guidance validity:**18 proposals explicitly abstain on status. A directly issued range can be well evidenced even if complete original/revision history is unavailable. The current single pass/fail result makes history incompleteness look like total range-extraction failure. That conservatism must remain visible in existing scores, but future design should distinguish base-guidance evidence validity, status/history validity and production eligibility rather than manufacture initial status.

## Smallest recommended corrections — not implemented

Priority1: separate validity of a **prior range as financial evidence** from validity of that prior range's own revision label. Only a compatible, available, adequately evidenced prior amount/metric/period/unit/basis may support current revision arithmetic. Its own status can remain unresolved. Current unsupported status must still remain unresolved and quarantined. Add a cached Agilent regression plus negative tests for wrong period/basis/unit, future reference, missing quote and withdrawal. This can be tested entirely from saved data, without another paid call.

Priority2: correct partial-boundary validation: verify each supplied bound against the approved fiscal calendar and fill only missing bounds with explicit derivation provenance. Contradictory supplied dates still block. Cache-based ADI positive/conflicting-end/unknown-calendar tests can cover this without inference.

Priority3: separate an exact `raw_literal` linked to a source span from a deterministically parsed Decimal value. Validate thousands grouping, currency and scale; preserve the original text. Do not simply remove arbitrary punctuation from source evidence or infer a dollar sign from nearby unrelated figures. This resolves representation ambiguity without weakening literal/source requirements.

Priority4: improve deterministic source packaging/association for complete headings, row/column identity and scope footnotes; request longer unique passages or validated structural IDs. Repeated/missing matches remain blocked until genuinely disambiguated. An outside heading is usable only if its relationship to the precise table/period is established, not merely because it appears nearby.

These are proposals, not implemented rules or revised success scores. Do not retroactively call consumed diagnostic examples fresh evaluation or count flagged candidates as accepted. Fresh releases remain untouched. No additional inference is warranted for deterministic dependency/calendar/literal issues before cached tests and policy review; any later approved calls should target unresolved semantic-evidence questions rather than repeat the whole completed batch.

## Preservation and budget

Original responses, model versions, raw counters, validation outputs, gold labels, candidate IDs, failed evaluation artifacts and reservations remain unchanged. The only experiment-ledger write in this review is the owner-authorized append-only budget-policy event. New operational ceiling$8; occupied$2.6009185; local headroom$5.3990815; original$1.12 remains held. This is not guaranteed provider/shared credit. Inference is paused, and billing/credit/quota errors stop without retry. Human review remains pending; no production guidance or live inputs were promoted.
