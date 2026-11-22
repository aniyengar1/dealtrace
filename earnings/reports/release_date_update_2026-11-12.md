# Release-date evidence update — November 12, 2026

No prediction was locked or backdated. Session 4 remains paused. Only evidence records were added; no code, forecast, guidance, financial actual, migration or website changes.

## SentinelOne: independently verified original

[Original official announcement](https://investors.sentinelone.com/press-releases/news-details/2026/SentinelOne-Announces-Date-of-Fiscal-Third-Quarter-2027-Financial-Results-Conference-Call-and-Participation-in-Upcoming-Investor-Conference/default.aspx), dated November 12, 2026, identifies SentinelOne (NYSE: S), Q3 FY2027 ended October 31, 2026, and explicitly states:

> Results will be released after market close on Thursday, December 3, 2026.

The 2 p.m. Pacific / 5 p.m. Eastern conference call is separately identified. It is not the results-publication time.

- Direct HTTP: **200**. Exact response body retained in `data/cache/earnings/release-leads/S-exact-3a34812800b483533dd1f0839a4447fcb9c6e86b778ad44218ca8a1d81744da5.body`.
- Actual retrieval: **2026-11-12T23:57:07.549302+00:00**.
- Completed verification: **2026-11-12T23:57:43.472150+00:00**.
- Raw body SHA-256: `3a34812800b483533dd1f0839a4447fcb9c6e86b778ad44218ca8a1d81744da5`.
- Verifier: **Codex**, full official-document direct HTTP review, **independently_verified**, not user_verified. Stockhouse/user/search leads were discovery only.
- Evidence version: `44c674b9-16d2-5a39-b330-225112d7752a` in `earnings/announcements/S.json`; full normalized visible text is also preserved there. Existing records were not overwritten.
- Timezone: America/New_York, documented conservative NYSE/US market-day interpretation; no exact publication clock time inferred.
- Validation: exact target/period, body hash and conservative deadline passed; subsequent strict source refresh also passed with actual retrieval evidence retained in the validation JSON.

## CrowdStrike and MongoDB: retrieval still blocked

| Company | Directory requested | Exact original announcement lead | Exact-page request / response time (UTC) | Result |
|---|---|---|---|---|
| CRWD | [supplied official directory](https://ir.crowdstrike.com/press-releases/) | [November 4 announcement lead](https://ir.crowdstrike.com/news-releases/news-release-details/crowdstrike-announces-date-fiscal-third-quarter-2027-financial) | checked 2026-11-12T23:57:07.109454+00:00; error response received 23:57:07.193877 | Directory and exact page both **403**; no announcement retrieved |
| MDB | [supplied official directory](https://investors.mongodb.com/news-events/news-releases) | [November 5 announcement lead](https://investors.mongodb.com/news-releases/news-release-details/mongodb-inc-announces-date-third-quarter-fiscal-2027-earnings) | checked 2026-11-12T23:57:07.194397+00:00; error response received 23:57:07.320603 | Directory and exact page both **403**; no announcement retrieved |

Search returned indexed official text supporting December 1 after-close leads and located the same exact original URLs, but it was not promoted to verification. There is no new `announcements/CRWD.json` or `announcements/MDB.json`. The purported December 1 dates remain unverified for locking. This is not a statement that either company has not announced its date.

The complete directory and exact-page attempts, actual response times, hashes and cached response paths are preserved in `earnings/validation/release_date_research_2026-11-12.json`. Error-response SHA-256 values identify **403 response bodies**, not an original announcement body. Previous evidence/report history remains unchanged. No wire-service or reprint domain was added to the allowlist or used as verified evidence.

## Eligibility windows

All verified dates below have after-close publication wording without an exact results timestamp. Use **midnight at the start of the release date**, America/New_York (EST, UTC−05:00); lock strictly before that boundary. Never use 16:00 Eastern or the conference call as the deadline.

| Company | Verified release date | Earliest 14-day eligibility | Strict deadline |
|---|---|---|---|
| OKTA | December 1, 2026 | November 17, 00:00 EST / 05:00 UTC | December 1, 00:00 EST / 05:00 UTC |
| CRM | December 2, 2026 | November 18, 00:00 EST / 05:00 UTC | December 2, 00:00 EST / 05:00 UTC |
| IOT | December 3, 2026 | November 19, 00:00 EST / 05:00 UTC | December 3, 00:00 EST / 05:00 UTC |
| S | December 3, 2026 | November 19, 00:00 EST / 05:00 UTC | December 3, 00:00 EST / 05:00 UTC |

CRWD and MDB have **no actionable lock window until verified**. If the December 1 leads are later independently verified, the corresponding conditional window would begin November 17 at 05:00 UTC, ending strictly before December 1 at 05:00 UTC. These conditional dates do not authorize locking.

**ADBE, PD, GTLB and LULU remain unverified.** Adobe's call listing is insufficient. No new qualifying source was established for the other three in this bounded research update; that does not mean no announcement exists.

No verified window was open at this update's actual execution time. When a window opens, manually refresh the original evidence as described in the preceding Session 3 review, then run `.venv/bin/python -m earnings.predict --lock`. It uses the actual database clock and independently checks fresh announcement evidence, already-public results, input freshness, guidance availability and historical inputs. A verified date alone does not guarantee eligibility. Nothing has been scheduled automatically, and no future waiting process was started.
