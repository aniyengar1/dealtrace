# Bounded Session 3 evidence review — November 12, 2026

**Session 4 remains paused. The prospective live gate remains pending: zero real live predictions.** This review makes one necessary code correction: categorical guidance predictions must not inherit prior-year growth-comparability blocks. No new features, forecast method, migration, website changes, merge, push or deployment. Prior accepted commits and reports remain intact.

Database evidence was exercised at 2026-11-12T23:45:05.824933+00:00; current recorded probabilities were selected as of 2026-11-12T23:45:06.119417+00:00. No lock command was executed during this review. Synthetic enforcement attempts were rolled back; the post-rollback real ledger count is 0. This report does not schedule future work automatically.

## 1. CrowdStrike and MongoDB verification history

The old `companies.json` records still retain their historical confirmed label, December 1 date, source URL, quote and verified_as_of November 11. They also retain failed direct HTTP observations. Session 2 then recorded an indexed-official-source observation on November 12 at 08:14:56 UTC. This is not a full-document HTTP retrieval, and no earlier full-body hash/retrieval timestamp was preserved for either company. The previous label was too strong for the subsequent strict live-lock evidence requirement.

A 403 does not invalidate an announcement or prove that no date was announced. The change is in **evidence sufficiency for locking**, not evidence of a changed release date. Under the current rule a snippet/indexed excerpt is a lead only; an independently retrieved full official document must establish company, fiscal period/year, publication wording, issue date, timezone/precision, body hash and actual retrieval time. A qualifying direct user confirmation is a separately attributed alternative; another agent is not the user.

| Company | Preserved earlier claim | Full-source check history | Current automatic-lock status |
|---|---|---|---|
| CRWD | December 1, 2026 after close; announcement dated 2026-11-04; [official lead](https://ir.crowdstrike.com/news-releases/news-release-details/crowdstrike-announces-date-fiscal-third-quarter-2027-financial) | legacy check 2026-11-11T23:48:27.312280+00:00: HTTP 403, no fetched_at; Session 3 check Nov 12 10:55 UTC: HTTP 403; this review 2026-11-12T23:43:43.907202+00:00: HTTP 403, fetched_at null | UNVERIFIED_RELEASE_DATE; no qualifying `announcements/CRWD.json` version |
| MDB | December 1, 2026 after close; announcement dated 2026-11-05; [official lead](https://investors.mongodb.com/news-releases/news-release-details/mongodb-inc-announces-date-third-quarter-fiscal-2027-earnings) | legacy check 2026-11-11T23:48:31.323477+00:00: HTTP 403, no fetched_at; Session 3 check Nov 12 10:55 UTC: HTTP 403; this review 2026-11-12T23:43:44.120860+00:00: HTTP 403, fetched_at null | UNVERIFIED_RELEASE_DATE; no qualifying `announcements/MDB.json` version |

History is preserved in `companies.json`, the accepted Session 2 audit, original Session 3 check records, and the new review check JSON. The lock CLI uses the stricter `announcements/` evidence path; do not use the legacy confirmed label alone to authorize a lock. Clear the gap with a complete official IR document, an allowed SEC announcement, or an explicitly attributed direct user confirmation; never manufacture the missing earlier fetch time.

## 2. Three distinct comparability questions

1. **Prior-year growth:** does current revenue share compatible scope with last year’s denominator? This gates annual hurdle growth and quarterly implied growth. Existing flags remain unchanged.
2. **Historical guidance/result label:** did the specific old guidance and actual measure the same period/consolidated reported basis? Each historical row has its own exact-ID review. This determines training eligibility, independently of current growth flags.
3. **Current categorical target:** is there an explicit range for the exact target quarter and consolidated reported metric? The current guides below establish that target. They do not establish comparability of a future, still-unreported result. That separate exact-guidance/actual review remains mandatory at scoring.

`predict.py` previously read `growth_comparability` and blocked the categorical baseline. That was incorrect: this method uses historical outcome frequencies and has no prior-year revenue denominator. The check is removed; new regression tests for CRM/OKTA/S prove that growth and pending-result flags do not bypass or preempt the independent publication gate. This is not an assertion that their YoY revenue is now comparable, and it does not clear a future known guidance/result scope mismatch.

| Company | Growth block retained | Historical labels | Current target evidence and prediction decision |
|---|---|---|---|
| CRM | Informatica contribution and pending Contentful/Fin acquisitions change consolidation scope. October Braze announcement adds uncertainty; explicit evidence reconciliation required. | 8/8 eligible; independent exact-version reviews | 11420000000–11500000000 USD, 2026-08-01–2026-10-31; `3b513a29-59c1-51a3-bf16-fa1001da216c`; [SEC 0001108524-26-000187, 99.1](https://www.sec.gov/Archives/edgar/data/1108524/000110852426000187/crm-q2fy27xexhibit991.htm); issued/filed 2026-08-26/2026-08-26. Explicit total consolidated reported revenue target; no separate target-basis conflict established by the preserved growth-only reasons. Categorical forecast must not inherit them. |
| OKTA | August 26 Permiso acquisition is a subsequent event with consideration still under evaluation. Annual guidance and prior-year comparison scope require reconciliation; partner-services shift is also disclosed. | 7/8 eligible; independent exact-version reviews | 813000000–817000000 USD, 2026-08-01–2026-10-31; `7790a72a-98d9-57b3-9287-bf22cba52401`; [SEC 0001660134-26-000068, 99.1](https://www.sec.gov/Archives/edgar/data/1660134/000166013426000068/okta-7312026_ex991.htm); issued/filed 2026-08-26/2026-08-26. Explicit total consolidated reported revenue target; no separate target-basis conflict established by the preserved growth-only reasons. Categorical forecast must not inherit them. |
| S | Observo and Prompt acquired in September 2025; current/prior remaining periods contain different ownership durations. Comparable revenue impact not reconciled. | 8/8 eligible; independent exact-version reviews | 309000000–311000000 USD, 2026-08-01–2026-10-31; `c5bf519b-08d3-5b8b-a2ad-bdd3636e8dba`; [SEC 0001583708-26-000052, 99.1](https://www.sec.gov/Archives/edgar/data/1583708/000158370826000052/sentineloneq227exhibit991.htm); issued/filed 2026-08-27/2026-08-27. Explicit total consolidated reported revenue target; no separate target-basis conflict established by the preserved growth-only reasons. Categorical forecast must not inherit them. |

Salesforce guidance explicitly includes Informatica contribution; pending/acquired businesses can still affect YoY comparability and eventual result review. Okta’s Permiso/partner-services concerns do not themselves prove that its total-revenue guide excludes the target quarter’s consolidated revenue. SentinelOne’s different prior-year ownership durations concern the growth denominator; both acquisitions predate this guide. We did not normalize any amount. Source quotes were reverified using the existing SEC fetcher; see `session3_evidence_review_targets.json`.

Current prediction blockers: CRM and OKTA are outside their 14-day windows; S lacks qualifying results-publication timing. All still require a fresh announcement check, successful SEC + official IR already-public-results checks, available/fresh actuals and guidance and eligible history at the real execution time. A pending actual is expected before a prediction; it blocks scoring, not the prediction.

## 3. Actual database enforcement attempts

All attempts below ran against real PostgreSQL inside a transaction that was fully rolled back. `service_role` is the application write role.

| Table / application role | UPDATE | DELETE | TRUNCATE |
|---|---|---|---|
| historical observations / service_role | rejected 42501 | rejected 42501 | rejected 42501 |
| live predictions / service_role | rejected 42501 | rejected 42501 | rejected 42501 |
| live results / service_role | rejected 42501 | rejected 42501 | rejected 42501 |

- Ordinary local-owner prediction UPDATE/DELETE and results TRUNCATE hit immutable triggers: SQLSTATE **55000**.
- A same-company/period/metric/method insert added no duplicate; a parallel method could insert a separate synthetic row. The unique key includes method_version.
- Application INSERT of made_at=2000-01-01 was rejected (**42501**, no timestamp-column INSERT privilege).
- An ordinary owner insert supplying that old timestamp stored **2026-11-12T23:45:06.090450+00:00** instead: the DB clock trigger overrides the supplied value.
- A later mutable legacy guidance-payload change left the locked self-contained snapshot unchanged. Locked guidance, historical inputs, source records, probabilities and evidence remain in immutable JSON, independent of later legacy table edits.
- Real prediction count after rollback: **0**. No synthetic attempt is a prospective prediction.

Details: `validation/session3_evidence_review_database.json`. A DBA/owner who can alter DDL can disable/drop enforcement or change grants; this does not protect against that administrator. It protects application writers and ordinary owner DML, not a hostile database administrator.

## 4. Eligible outcomes and probabilities

Counts and probabilities below use the actually recorded immutable observations as of the DB time above. They are diagnostic current rates, not locked predictions or calibrated confidence. All ten use own-company history; no pooled fallback is needed. If own eligible N<6, require >=12 pooled outcomes from >=2 companies; otherwise block.

| Company | Eligible / captured | below / within / above counts | P(below) | P(within) | P(above) |
|---|---|---|---|---|---|
| ADBE | 8/8 | 0/0/8 | 0E-24 | 0E-24 | 1.000000000000000000000000 |
| CRM | 8/8 | 0/4/4 | 0E-24 | 0.500000000000000000000000 | 0.500000000000000000000000 |
| CRWD | 7/8 | 0/0/7 | 0E-24 | 0E-24 | 1.000000000000000000000000 |
| GTLB | 7/8 | 0/0/7 | 0E-24 | 0E-24 | 1.000000000000000000000000 |
| IOT | 8/8 | 0/0/8 | 0E-24 | 0E-24 | 1.000000000000000000000000 |
| LULU | 8/8 | 2/0/6 | 0.250000000000000000000000 | 0E-24 | 0.750000000000000000000000 |
| MDB | 7/8 | 0/0/7 | 0E-24 | 0E-24 | 1.000000000000000000000000 |
| OKTA | 7/8 | 0/0/7 | 0E-24 | 0E-24 | 1.000000000000000000000000 |
| PD | 7/8 | 0/3/4 | 0E-24 | 0.428571428571428571428571 | 0.571428571428571428571429 |
| S | 8/8 | 0/1/7 | 0E-24 | 0.125000000000000000000000 | 0.875000000000000000000000 |

All rows use the same rule: latest guidance with both issuance-interval end and SEC filing date <= D−15, before entry to the D−14 release window; never guidance published with/after the result. The earliest observed completed-quarter indication defines the historical selection anchor. Eligible labels additionally require the actual and release SEC availability and an exact-version basis review. The latest eight captured quarters include excluded rows; no ninth-quarter replacement. Live rates also require recording time <= prediction time, and later revisions cannot enter an earlier view. Decimal probabilities sum exactly to one (first two rounded half-even at 24 places, above receives residual); no smoothing.

| Excluded quarter | Early indication | Exact reason / source |
|---|---|---|
| CRWD Q1 FY2026, 2025-02-01–2025-04-30 | 2025-05-07; formal release 2025-06-03 | [SEC 0001104659-25-045244](https://www.sec.gov/Archives/edgar/data/1535527/000110465925045244/tm2514190d1_8k.htm); EARLY_POST_CLOSE_RESULT_INDICATION: 2025-05-07 precedes formal-release lock window; excluded rather than training on already-public result information |
| GTLB Q1 FY2027, 2026-02-01–2026-04-30 | 2026-05-11; formal release 2026-06-02 | [SEC 0001653482-26-000095](https://www.sec.gov/Archives/edgar/data/1653482/000165348226000095/gtlb-20260511.htm); EARLY_POST_CLOSE_RESULT_INDICATION: 2026-05-11 precedes formal-release lock window; excluded rather than training on already-public result information |
| MDB Q3 FY2026, 2025-08-01–2025-10-31 | 2025-11-03; formal release 2025-12-01 | [SEC 0001628280-25-047941](https://www.sec.gov/Archives/edgar/data/1441816/000162828025047941/a2025-11x03xpressrelease.htm); EARLY_POST_CLOSE_RESULT_INDICATION: 2025-11-03 precedes formal-release lock window; excluded rather than training on already-public result information |
| OKTA Q4 FY2025, 2024-11-01–2025-01-31 | 2025-02-04; formal release 2025-03-03 | [SEC 0001660134-25-000015](https://www.sec.gov/Archives/edgar/data/1660134/000166013425000015/okta-20250204.htm); EARLY_POST_CLOSE_RESULT_INDICATION: 2025-02-04 precedes formal-release lock window; excluded rather than training on already-public result information |
| PD Q1 FY2027, 2026-02-01–2026-04-30 | 2026-05-11; formal release 2026-05-28 | [SEC 0001140361-26-020610](https://www.sec.gov/Archives/edgar/data/1568100/000114036126020610/ef20072978_ex99-1.htm); EARLY_POST_CLOSE_RESULT_INDICATION: 2026-05-11 precedes formal-release lock window; excluded rather than training on already-public result information |

These five preliminary/in-line/post-close reaffirmation indications precede the later formal release window. They are conservatively excluded for timing ambiguity, not asserted to contain a full precise revenue result. The identical exclusion criterion applies across companies. All guidance versions and raw quotes remain in the historical files. Historical eligible total remains 75/80 (2 below, 8 within, 65 above). No probabilities, counts, historical observations or evaluation results changed in this review. The 57-case reconstruction remains retrospective and provides no validated predictive-quality claim.

## 5. Manual lock schedule

All three verified announcements refer to **results publication after US market close**, with a separately described webcast. No exact results clock time is asserted. The conservative deadline is start of the release day in America/New_York (EST, UTC−05:00 on these dates), and locking must be strictly before it.

| Company | Official dated publication evidence | Earliest 14-day eligibility | Strict deadline | Current remaining gates |
|---|---|---|---|---|
| OKTA | [2026-11-02 official announcement](https://investor.okta.com/news-and-events/news-releases/news-details/2026/Okta-to-Announce-Third-Quarter-Fiscal-Year-2027-Financial-Results-on-December-1-2026/default.aspx); release 2026-12-01 after close. Latest full fetch 2026-11-12T23:48:24.057067+00:00; fresh_full_document_hash_matches | 2026-11-17 05:00 UTC = 2026-11-17 00:00 EST | 2026-12-01 05:00 UTC = 2026-12-01 00:00 EST | Outside window now; rerun fresh source, already-public-results, freshness and guidance/history checks when inside. No inherited growth block. |
| CRM | [2026-11-10 official announcement](https://investor.salesforce.com/news/news-details/2026/Salesforce-Announces-Date-of-Third-Quarter-Fiscal-2027-Earnings-Release-and-Webcast/default.aspx); release 2026-12-02 after close. Latest full fetch 2026-11-12T23:48:23.748309+00:00; fresh_full_document_hash_matches | 2026-11-18 05:00 UTC = 2026-11-18 00:00 EST | 2026-12-02 05:00 UTC = 2026-12-02 00:00 EST | Outside window now; rerun fresh source, already-public-results, freshness and guidance/history checks when inside. No inherited growth block. |
| IOT | [2026-11-02 official announcement](https://investors.samsara.com/news/news-details/2026/Samsara-to-Announce-Third-Quarter-Fiscal-Year-2027-Financial-Results-on-December-3-2026/default.aspx); release 2026-12-03 after close. Latest full fetch 2026-11-12T23:48:24.370175+00:00; fresh_full_document_hash_matches | 2026-11-19 05:00 UTC = 2026-11-19 00:00 EST | 2026-12-03 05:00 UTC = 2026-12-03 00:00 EST | Outside window now; rerun fresh source, already-public-results, freshness and guidance/history checks when inside. No inherited growth block. |

CRWD and MDB: December 1 remains a lead; if later independently verified, the corresponding hypothetical date-only window would open November 17 05:00 UTC and close strictly before December 1 05:00 UTC. **These are not authorized lock dates while evidence is unverified.** PD, GTLB, S, ADBE and LULU have no qualifying release-date evidence, so no lock window can be assigned. Adobe’s December 9 14:00 Pacific entry is a call, not a verified publication time. See the original report for official IR leads; this review does not invent new dates or imply that a company has not announced one.

Fresh-source checks initially rejected changed raw body hashes for CRM/OKTA/IOT. A full comparison found unchanged normalized visible text for CRM/IOT, and only email-alert form validation/captcha text changes for OKTA; release wording was unchanged. Codex appended new evidence versions at the real review-entry time, retaining every old version/ID/body reference. The subsequent strict refresh passed all three. The strict raw-hash policy is unchanged: future footer/HTML changes can conservatively block again and require another reviewed version.

### Exact manual workflow (no scheduler)

When a verified window opens, first check the original sources using the existing helper. This performs direct HTTP, prints actual retrieval evidence and fails closed on inaccessible/changed sources:

```sh
cd /Users/anirudhiyengar/dealtrace-earnings
.venv/bin/python - <<'PY_REFRESH'
from earnings.registry import companies
from earnings.live import announcement, refresh_announcement
from earnings.models import dumps
for ticker in ('OKTA', 'CRM', 'IOT'):
    company = companies()[ticker]
    print(dumps(refresh_announcement(company, announcement(company))))
PY_REFRESH
```

If blocked, stop that company: read the complete newly cached official document and verify company, fiscal quarter/year, issue date, publication wording, timezone/precision. Append a new version to its `earnings/announcements/<ticker>.json` only after review, carrying previous_evidence_id, actual verifier, the new checked_at/retrieved_at/body hash/cache path, and a newly generated real verified_at and ID. Do not overwrite old versions, copy an old timestamp onto a new check, label another agent user_verified or promote a snippet. Use the schema of the appended review versions as the template. A changed date requires a new deadline; never edit an existing lock. A direct user confirmation must preserve named supplied_by and actual entered_at and remain user_verified, not independently_verified. The existing manual_dates command records confirmations but does not automatically publish them to the lock registry.

Update SEC actuals and reviewed guidance before locking (manual guidance changes must preserve versions and dates):

```sh
.venv/bin/python -m earnings ingest ALL --refresh
.venv/bin/python -m earnings load-guidance ALL
.venv/bin/python -m earnings.predict --lock
```

The lock command generates its own unique execution file from the **actual PostgreSQL time**. It rechecks sources and already-public results for eligible companies; the preparatory check does not substitute for those checks. Do not supply an as-of timestamp or backdate a filename to claim a live prediction. A source-access/publication/freshness/guidance failure leaves that company blocked while others continue. Review the printed `locked` and `skipped` entries; a timing window alone never guarantees a lock. **No cron, daemon or automatic future scheduling has been installed; nothing is waiting for a future date.**

## Correction validation and stop

New tests for CRM/OKTA/S show a growth-only block and missing future outcome do not prevent the distinct publication check. The complete suite passes **364 tests, 3 skipped**; the targeted live-baseline suite passes **29 tests**. The existing timing, historical-leakage, source-verification, immutable-clock/snapshot, duplicate and scoring checks remain passing. No schema/method/probability changes were made. Original reports are historical records; this review supersedes their assertion that growth flags automatically block categorical predictions.

Commit scope: necessary correction in `earnings/predict.py`, regression tests, corrected current instructions, appended announcement evidence, and this evidence review. Existing growth flags, historical labels, prior lock execution record, original commits and interface work remain unchanged. No new live prediction exists. Stop for review; do not start Session 4.
