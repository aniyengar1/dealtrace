# Live-lock readiness review — no enforcement changes

No Vertex, CountTokens, SEC or IR requests were made in this review. No live predictions were created. Simulated time is confined to a test module and in-memory SQL-clock adapter; production clock code, database guards, manual guidance, probability methods and checkpoint tags are unchanged. The separate owner-authorized budget update lowers only the extraction experiment ceiling and pauses inference.

## Origin and exact meaning of the freshness rules

The ten-minute constant first appeared in **commit94ce788**, November12,2026, in `0103_crosscheck_live_ledger.sql` as an implementation-chosen, fail-closed operational TTL. It is not an SEC/accounting standard, a playbook-prescribed number, a statistically calibrated threshold, or the separate owner-approved135/150-day financial-input policy.

At prediction INSERT, migration0103 assigns `made_at=clock_timestamp()` and checks:

- `announcement.checked_at` must exist, not be in the future and be **no earlier than made_at−10minutes**. Equality at ten minutes passes; one microsecond older fails. Source URL and time precision must be present.
- `publication_check.checked_at` must likewise be within **two minutes**, with status `not_observed`, successful SEC and official-IR checks, and exact target boundaries. Equality at two minutes passes. Missing/future times fail.
- Creation time is generated separately for each method row. Checks near expiry can become stale between application evaluation and insertion; use margin rather than aiming at exact TTL limits. Both-method insertion is one transaction.

The application `refresh_announcement` currently redownloads the full independent HTTP announcement and requires its raw body hash to match the reviewed evidence. A footer/captcha/HTML change can therefore block an unchanged schedule. This happened in the November12 review and required appended source versions; old versions were retained.

Migration0105/commit7dc952c extended a ten-minute requirement to **owner-reported original retrieval** for the PDF route. The application also rejects older owner retrieval and does not freshen it by hashing. This was deliberately conservative, but it conflates durable historical evidence with a current-state check and is too restrictive for an unchanged historical announcement.

### Durable evidence versus a fresh check

The original announcement/PDF remains valid **historical evidence** of what was announced. Preserve its true supplier, retrieval, ingestion, review time, exact wording, URL and hash. Its integrity does not establish authenticity or prove that the schedule is still current. It should not expire merely because ten minutes passed, and an unchanged document need not be downloaded again to retain evidentiary value.

A **new current-state check** answers different questions: has the schedule changed, and are results or preliminary indications already public? It needs its own observer, exact pages, actual check times, observations and provenance. A local hash check answers neither question. An empty SEC feed cannot establish that results are not already on the company website.

No enforcement change is implemented here. The current code can still block an old owner PDF as described above. The recommended change is to retain that durable document and require a separate recent schedule/publication check, rather than demand a new retrieval of the same historical file. Explicit owner approval is needed before modifying the current application/SQL enforcement and creating a new checkpoint.

## Proposed auditable pre-lock procedure — approval required

1. **Prepare before the short freshness window:** ingest/review SEC facts and manual guidance, check schema/permissions and duplicate status, preserve the original announcement/PDF and verify its hash. Resolve issuer, target quarter, announcement date, explicit results-publication date, timezone and precision. No date is inferred from a call time. CRWD/MDB original PDFs and exact article URLs are still outstanding.
2. **Check current schedule:** automated direct HTTP when available; otherwise the owner personally opens the exact official announcement and current official news/results pages. Merely opening the old locally saved PDF is not a current-state check. Read actual results-publication wording and any update/rescheduling notices; a re-download of unchanged historical evidence is unnecessary.
3. **Check for already-public results:** separately refresh SEC submissions through the existing fetcher AND inspect a complete observable official-IR news/results inventory, including preliminary/in-line indications and updates since target-quarter end. Owner browser observations may replace an inaccessible automated IR inventory only under the proposed approved route. Absence of SEC filings alone is never sufficient. Empty, cached/incomplete, inaccessible or ambiguous inventories block; so do possible target results until disambiguated.
4. **Record a contemporaneous attestation:** named owner; actual timezone-aware time and precision for each exact URL; what was observed; coverage/pagination; release date/session seen; whether results/preliminary indications were found; all access gaps; references to the durable evidence ID/hash; optional saved page/screenshot hashes; and the actual later ingestion time. Label it `user_verified`, not independently HTTP-verified by Codex. Do not invent or backdate timestamps. Hashes prove integrity, not truth.
5. **Run promptly with actual DB time:** recommended initial policy retains ten minutes for schedule checks and two minutes for publication checks, measured from the oldest necessary page check, not a new file-ingestion timestamp. Refresh SEC metadata within the same two-minute window. For the first Okta lock this is one company's packet, not ten simultaneous owner attestations. If checks expire, repeat the current-state check, not the unchanged historical document download. Any changed schedule requires appended evidence and re-evaluation before locking; never rewrite an old lock.
6. **Lock both methods only after all gates pass:** same target guidance/history/cutoff, separate method versions, DB-generated creation times, immutable snapshots and duplicate protection. Source checks are bounded observations, not universal internet surveillance. Stop on ambiguity or already-public results.

Suggested attestation wording (a proposal, **not an actual owner attestation**): “I personally checked the listed official pages at the recorded times. The observed schedule was [date/session/precision]. I reviewed the described news/results coverage for [exact fiscal quarter], including preliminary results. I [did/did not] observe target-period results or indications. All access or coverage gaps are listed.” If results are found or coverage is uncertain, block rather than attest success.

### Exact official URL checklist

These URLs are from existing configuration or the saved official Okta document; this review did not verify current accessibility.

|Company|Purpose|URL|
|---|---|---|
|OKTA|Original dated announcement|https://investor.okta.com/news-and-events/news-releases/news-details/2026/Okta-to-Announce-Third-Quarter-Fiscal-Year-2027-Financial-Results-on-December-1-2026/default.aspx|
|OKTA|Current official news inventory|https://investor.okta.com/news-and-events/news-releases/default.aspx|
|OKTA|Quarterly-results inventory (link present in saved official HTML)|https://investor.okta.com/financials/quarterly-results/default.aspx|
|OKTA|SEC submissions, checked independently of IR|https://data.sec.gov/submissions/CIK0001660134.json|
|CRWD|Current configured news inventory|https://ir.crowdstrike.com/news-and-events/news-releases|
|CRWD|Owner's official discovery-page lead|https://ir.crowdstrike.com/press-releases/|
|MDB|Official news inventory|https://investors.mongodb.com/news-events/news-releases|

CRWD/MDB **exact original article URLs must come from the supplied evidence**; a directory link is not announcement verification. The owner should record the exact reachable final official URL, redirects and inventory pages actually inspected. No third-party reprint or search excerpt silently replaces official evidence.

### Specific policy approval needed before code changes

Approve a “durable announcement + contemporaneous pre-lock check” policy that:

- accepts attributed owner browser schedule/publication attestations as an alternative to automated official-IR access;
- moves freshness to the new current-state check times, retaining true original PDF retrieval permanently;
- replaces0105's original-retrieval age condition and0103's overloaded announcement-check field with explicit, referenced pre-lock check provenance;
- defines required coverage/fail-closed behavior and retains10/2-minute TTLs unless a separate change is approved;
- permits meaningful schedule/source-text review instead of treating every raw HTML/footer hash change as a schedule change.

This requires reviewed application changes and a new migration/checkpoint; existing migrations/tags must remain preserved. It does not change the conservative start-of-release-date deadline, actual DB timestamps, historical cutoff, methods, guidance selection, probability normalization or immutable snapshots. I have not implemented this proposal.

## Okta boundary rehearsal

[Read-only rehearsal evidence](../validation/okta_boundary_read_only_review.json) used actual stored Okta inputs and a **test-only** clock. Actual execution: November14,2026,13:23:00.727626–13:23:01.308026America/Los_Angeles. PostgreSQL READ ONLY; production INSERT was replaced by an in-memory capture; history ingestion suppressed; no network calls. SQL INSERT guards were **not executed with simulated time**; only their TTL expressions were separately tested. This is an application-boundary rehearsal, not a live prediction or future source verification.

Assuming the December1 New York release date remains unchanged:

- Opening: **November16,2026,21:00Pacific = November17,05:00UTC**.
- Strict deadline: **December1,00:00America/New_York = December1,05:00UTC**. After-close wording is not permission to wait until16:00.

|Controlled test time/mode|Result|
|---|---|
|Opening−1microsecond|OUTSIDE_14_DAY_WINDOW;0candidates|
|Exactly opening, hypothetical clean/fresh source checks|2conditional candidates, one per method|
|Opening+1microsecond, same hypothetical checks|2conditional candidates|
|Exactly deadline|LOCK_DEADLINE_PASSED;0candidates|
|Opening with unchanged stored November12 checked_at only|0103 announcement TTL expression would reject;0candidates|
|Synthetic announcement403|ANNOUNCEMENT_ACCESS_GAP|
|Synthetic changed raw announcement hash|ANNOUNCEMENT_SOURCE_CHANGED|
|Synthetic publication403 or incomplete/loading inventory|PUBLICATION_CHECK_BLOCKED|
|Synthetic observed IR results or possible SEC results|PUBLICATION_CHECK_BLOCKED|
|Synthetic publication check121seconds old|0103 publication TTL expression would reject|

No actual future-source check is represented by those fixtures. The live ledger remained **0before/0after**.

Conditional candidates share guidance **7790a72a-98d9-57b3-9287-bf22cba52401**, Q3FY2027(August1–October31,2026), **$813–817million**, issued/filedAugust26, accession0001660134-26-000068. Both share the exact seven history IDs and cutoff. Counts0below/0within/7above produce empirical(0,0,1) and Laplace(0.1,0.1,0.8). Full IDs are in the rehearsal artifact. Those are conditional preparations, not calibrated certainty or recorded predictions.

### Every first-lock gate and present readiness

|Gate|Present assessment / blocker|
|---|---|
|Actual time within window|Currently before opening; cannot lock early. Re-evaluate with actual DB time.|
|Durable exact-period announcement/date/timezone|Existing reviewed Okta version4a3e1f16-7b0b-55be-b00b-f43055db57af supports Dec1 after close, New York date boundary. It does not prove the future schedule is unchanged.|
|Fresh schedule/announcement check|Not performed for the future opening. Current enforcement needs a successful full HTTP/hash refresh; inaccessible/changed HTML blocks. Owner-browser alternative needs the policy approval above.|
|Fresh SEC+IR already-public-results check|Not performed for the future opening. Any observed/suspected results, partial inventory, access failure, missing/future/stale timestamp or target mismatch blocks. No inference from absent filings.|
|Guidance available at frozen horizon|Current snapshot passes: exact target/metric/company, nonwithdrawn, issued/filedAug26 before Nov17 anchor. New guidance or withdrawal by actual execution must be reviewed; both methods freeze the same selected version.|
|Financial input freshness|At boundary, current guidance age83days <=150; latest actual period endJul31 age109days <=135. Current snapshot passes. Missing facts, changed data or expiry would block.|
|History and probabilities|Current snapshot has seven own eligible quarters, sufficient and fully recorded/public by the test cutoff. Counts/normalization pass; both share exact IDs. New blocked/corrected versions must be selected honestly, not ignored.|
|Already-stored target actual|Currently0target rows, but that is not evidence that results are not public elsewhere. Any target actual arriving before lock blocks.|
|Duplicates/paired methods|Currently0target prediction rows. A pre-existing partial pair blocks for review; complete pairs skip rather than duplicate.|
|DB schema/access/enforcement|Read-only metadata confirms0103–0105 applied, service-role INSERT columns available, made_at INSERT forbidden and UPDATE forbidden. Actual DB timestamp, snapshot/availability/probability guards still apply at real insertion.|
|Growth/result comparability flags|Okta's Permiso/prior-year growth block is not a categorical-prediction blocker. Future guidance-to-actual scoring still needs its own basis review; an unreported result blocks scoring, not prediction.|

[Database metadata evidence](../validation/okta_readiness_db_metadata.json). No immutable lock is guaranteed by the rehearsal: real source checks, fresh input review and actual DB insertion must still succeed at the opening. No future job was scheduled.

## Offline diagnostic analysis

See [separate failure review](diagnostic_failure_review_2026-11-14.md). Original outputs, scores and reservations are preserved; recommendations are not implementations or improved performance claims.

## Verification and budget status

**88 targeted tests passed** with network denied for hybrid tests; no root DB-migration fixture was loaded for these local unit tests. The12-case application rehearsal used a separate READ ONLY connection and self-asserted its results. No production clock code or live enforcement changed. All checkpoint tags and protected live code match the accepted r2 version.

The separately authorized budget update is persisted: ceiling$8, occupied$2.6009185, local headroom$5.3990815; original$1.12 remains held. Inference is paused. Headroom is not guaranteed shared credit. Billing/credit/quota errors stop without retry; no billing/account changes. [Budget report](budget8_update_2026-11-14.md), [preservation evidence](../validation/readiness_review_preservation.json).
