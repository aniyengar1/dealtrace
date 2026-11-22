# Crosscheck preparation before Session 3

This is a bounded preparation pass after accepted Session 2 commit `f985cea`.
No baseline probabilities, training, prediction ledger, merge, push or deployment
was performed. Crosscheck remains the module name and `/crosscheck` its route.

## Experimental forecast flag

`CROSSCHECK_EXPERIMENTAL_ANNUAL_FORECAST` is a **server-only feature flag**.
Absent, empty, `false`, or any value other than the exact string `true` means off.
It is checked at request time; no `NEXT_PUBLIC_` variable or client toggle exists.

With the flag off:

- Search summaries omit forecast status/verdict fields before client rendering.
- Company pages omit annual estimates, verdicts, benchmarks and forecast evaluation.
- Evidence JSON omits `forecast`, `forecast_display`, `evaluation`,
  `evaluation_display`, and forecast/evaluation-only change messages/coverage notes.
- Annual guidance, actuals, annual hurdles, history and source evidence remain.
- Existing stored quarterly calculations are now visible at the **same exact
  report cutoff**, with their own periods, guidance, denominator and evidence.
  There is no fallback to a different date and no calculation in browser floats.
  Display scaling/rounding uses PostgreSQL NUMERIC and text; source values remain
  Decimal strings. Missing quarter records have an explicit unavailable state.
- Quarterly guidance-implied growth compares the full quarterly range with prior
  comparable-quarter revenue. It is not a forecast; no annual YTD subtraction is
  applied. Blocked growth comparisons remain blocked.

The published overview snapshots remain dated November 11; the November 12 audit
calculations were not silently substituted into an older overview. Quarterly data
is selected at each displayed overview’s exact cutoff.

The prior interface did **not** display the already implemented quarterly path;
this was found during preparation and corrected using its existing tables, not
by creating a new forecasting method. The internal annual forecast implementation,
case definitions, evaluation records and stored report payloads remain intact.
The public JSON is a presentation projection of the stored report ID, not a new
financial snapshot or a confidentiality/access-control boundary. Existing RLS
and authorized internal research access are unchanged.

For deliberate local experimental review only:

```sh
CROSSCHECK_EXPERIMENTAL_ANNUAL_FORECAST=true npm run start -- --hostname 127.0.0.1 --port 3014
```

Run from `apps/web` after a build. The opt-in view still labels the method
experimental/unvalidated. It is not the playbook's quarterly probabilistic
baseline and has no live track record. No environment file was read or changed
by the agent to configure this flag.

## Merge-readiness source review — no merge

Common ancestor: `5f5ed35ae0d09cf70fd9a7826bf0e151cdb5e27a`.
Current main reviewed: `50a582d0a28f213d0a8c561e9dbb213f13731bc8`.
This is a snapshot of main, not a promise against future changes. The other
agent's checkout and branch were not modified; git objects were read directly.

Every **shared frontend file** changed by earnings relative to that ancestor:

| Shared file | Earnings change | Current main / coordination |
|---|---|---|
| `apps/web/src/app/layout.tsx` | One intentional Crosscheck navigation link | Main retains the ancestor version. Preserve this addition; validate header spacing visually. No deal routes/components were edited. |
| `apps/web/package.json` | Adds pinned `@tailwindcss/postcss` 4.3.3 dev dependency | Main retains the ancestor version. Review shared CSS pipeline choice with the deals agent. |
| `apps/web/package-lock.json` | Adds that plugin's package/root dev-dependency entries | No existing package version changed. No dependency installation or lockfile regeneration was needed in this pass. |
| `apps/web/postcss.config.mjs` | New shared Tailwind v4 PostCSS configuration supporting the Webpack build | Absent on main. It affects all routes, not only Crosscheck; it is not a scoped route stylesheet. |

All other frontend changes are additions/changes under the Crosscheck page, API
and library/test namespaces. `globals.css`, the body font, root reset import,
`next.config.ts`, the database adapter, proxy and existing deal-page source remain
unchanged by earnings. Current main's only frontend change is
`apps/web/src/lib/labels.ts` (additional deal vocabulary/display overrides), which
earnings did not edit. A normal future merge must retain those main changes;
copying the earnings app wholesale would lose them.

The sets of tracked paths changed on both branches have **no overlap** at the
reviewed commits. There is therefore no overlapping-path textual conflict to
resolve in this snapshot. This is not an actual merge result: no merge command,
branch switch, merge-tree write, rebase or modification of main was used.
Main's new deals migrations 0010/0011 and discovery work are independent of the
earnings 0100+ namespace. Existing `AGENTS.md` remains earnings-worktree-specific;
its placement/instructions must be reviewed before adopting it as main's global
agent instructions. It was not rewritten here.

### Global styling, reset and dependency checks

The source `@import "tailwindcss"` reset and body font are byte-identical on main
and earnings. Tailwind is pinned to 4.3.3 on both. Runtime Next/React dependencies
are unchanged. The only added lockfile package is `@tailwindcss/postcss`; no
existing package version changed.

A canonical Tailwind 4.3.3 compile used each branch's CSS/source candidates with
the **same installed compiler**. Comparing selector/property declaration keys
found **zero changed and zero removed existing keys**; 530 keys were added for
the additional source candidates/theme variables. Existing base/reset and shared
utility declaration values were unchanged. This is static CSS evidence, not
computed browser styles, a screenshot test, or proof that both bundlers behave
identically. No verified styling leakage was found to justify changing global
CSS or deal styling in this pass.

Main configures the Tailwind Turbopack CSS loader. Earnings additionally supplies
PostCSS for its verified Webpack path. Before merging, coordinate one supported
shared CSS pipeline and verify Turbopack/PostCSS interaction rather than assuming
the two processing paths are identical. The earnings Webpack production build,
TypeScript and lint checks pass. The main build was not silently modified to
make it match earnings.

### Representative deal pages and visual status

**Visual compatibility remains UNVERIFIED. No screenshots were generated.**
The standing prohibition on Chrome/browser automation remains in effect. A
matching browser/viewport/data screenshot comparison between current main and
earnings was not run. There is no fabricated viewport, screenshot or pixel
comparison in the evidence (`screenshots: []`). This visual gate remains open.

As a narrower control, direct local HTTP requests to the earnings build checked
`/`, `/deals/zendesk`, `/deals/splunk` and `/review/zendesk` in both forecast flag
modes, using identical request defaults and the same local database. All returned
200 and had identical extracted text hashes. Intentional Crosscheck navigation
was present. This checks that the feature flag is isolated from existing deal
page output; it is **not** the requested main-versus-earnings visual comparison.
Main's label changes can also produce intentional deal-text differences, so a
future screenshot comparison must isolate earnings effects from those changes.

CSS hashes, main/base revisions, direct-HTTP checks and the explicitly empty
screenshot inventory are stored in
`earnings/validation/pre_session3_readiness.json`. Canonical CSS and captured HTML
are local `/tmp` artifacts, not screenshots. No visual approval is claimed.

## Six unverified results-publication dates

These are **results-release** gaps as of the Session 2 source-check times on
November 12, not a fresh assertion that no announcement exists anywhere.

| Company | Official IR URL | Evidence gap |
|---|---|---|
| PagerDuty (PD) | https://investor.pagerduty.com/news/default.aspx | Direct page retrieved but news requires JavaScript/loading; no dated FY2027 Q3 publication announcement verified. Late-November window is historical inference only. |
| GitLab (GTLB) | https://ir.gitlab.com/news/default.aspx | Direct news page retrieved but shows loading content; no dated FY2027 Q3 results-publication announcement verified. |
| Samsara (IOT) | https://investors.samsara.com/news/default.aspx | Direct listing did not establish the exact FY2027 Q3 release date; historical early-December window is not confirmation. |
| SentinelOne (S) | https://investors.sentinelone.com/press-releases/ | Correct official listing retrieved after an earlier URL returned 404, but loading content did not verify a FY2027 Q3 publication date. |
| Adobe (ADBE) | https://www.adobe.com/investor-relations.html | Page lists **December 9, 2026, 14:00 Pacific earnings CALL**. That is not explicit confirmation of when financial results will be published. Page publication date is unknown. |
| Lululemon (LULU) | https://corporate.lululemon.com/investors/news-and-events/events-and-presentations | Official landing/event pages retrieved; no exact FY2026 Q3 results-publication date verified. Earlier attempted quarterly-results path returned 404. |

Individual actual check/fetch timestamps and failures remain in
`earnings/reports/audit_2026-11-12-date-checks.json`. Salesforce December 2 and
CrowdStrike/Okta/MongoDB December 1 have dated official results-release evidence.
CrowdStrike/MongoDB direct HTTP HTML/PDF still returned 403; official indexed
source confirmation is recorded separately from an actual HTTP fetch. None of
these observations supplies an invented exact publication clock time.

## Manual information intake

No manual confirmations have been received or added in this pass. For future
user-supplied **results-publication** information, preserve the supplied identity,
source URL, release date, timezone and stated precision. Do not silently convert
an earnings-call listing into a results-release confirmation.

Prepare a JSON file with these exact keys; replace placeholders with supplied
information, retaining null for genuinely unknown timezone/time:

```json
{
  "company": "PD",
  "supplied_by": "<user name or identifier>",
  "source_url": "https://investor.pagerduty.com/<official-announcement>",
  "release_date": "YYYY-MM-DD",
  "timezone": null,
  "time_precision": "date",
  "release_time": null
}
```

```sh
.venv/bin/python -m earnings.manual_dates supplied-confirmation.json
```

The append-only local observation file defaults to gitignored
`data/cache/earnings/manual-date-confirmations.jsonl`. Each entry gets a real UTC
`entered_at`, `verification_status: user_verified`, `independently_checked: false`
and a content-derived observation ID. Caller-supplied entry/verification
timestamps and extraneous verification fields are rejected. The command does
not publish to the registry, invent an announcement issuance time or backdate
historical availability. Date-only precision keeps a null clock time; hour,
minute and second precision must match the supplied clock text and IANA timezone.
`market_session` preserves `before_market_open`, `after_market_close` or
`during_market_hours` without inventing a precise time. Independent verification
must be a later, separately sourced observation, not an overwrite of the user's
original entry. A late manual entry cannot establish that a prediction was made
prospectively before the entry/verification existed.

## Session 3 readiness

| Company | Current quarterly guidance | Versions | Completed historical outcome quarters | Additional completed quarters needed |
|---|---|---:|---:|---:|
| PagerDuty | Q3 FY2027, Aug 1–Oct 31, 2026; initial Aug 27 | 1 | 0 | 8 |
| GitLab | Q3 FY2027, Aug 1–Oct 31, 2026; initial Sep 1 | 1 | 0 | 8 |
| Salesforce | Q3 FY2027, Aug 1–Oct 31, 2026; initial Aug 26 | 1 | 0 | 8 |
| CrowdStrike | Q3 FY2027, Aug 1–Oct 31, 2026; initial Aug 26 | 1 | 0 | 8 |
| Okta | Q3 FY2027, Aug 1–Oct 31, 2026; initial Aug 26 | 1 | 0 | 8 |
| Samsara | Q3 FY2027, Aug 2–Oct 31, 2026; initial Sep 3 | 1 | 0 | 8 |
| MongoDB | Q3 FY2027, Aug 1–Oct 31, 2026; initial Sep 1, reaffirmed Sep 28 | 2 | 0 | 8 |
| SentinelOne | Q3 FY2027, Aug 1–Oct 31, 2026; initial Aug 27 | 1 | 0 | 8 |
| Adobe | Q4 FY2026, Aug 29–Nov 27, 2026; initial Sep 10 | 1 | 0 | 8 |
| Lululemon | Q3 FY2026, Aug 3–Nov 1, 2026; initial Sep 3 | 1 | 0 | 8 |

There are eleven versions but only ten distinct **pending** targets. A
reaffirmation is not another quarter. The current unreported quarter does not
count toward eight completed historical guidance/outcome cases. Raw historical
companyfacts are available, but reviewed historical quarterly guidance, versions,
as-of selection and matched outcome-basis evidence are not yet backfilled.

Before baseline probabilities or immutable locks can be claimed, Session 3 needs:

1. Eight prior completed quarters per company (80 company-quarter cases before
   any comparability exclusions), all guidance versions and exact SEC evidence;
   corresponding earliest reported actuals and independent result-basis reviews.
2. A documented quarterly guidance-selection rule and treatment of original,
   latest, withdrawn/reinstated and point ranges. Inclusive endpoints already
   exist; history must be frozen before each result, never revised retrospectively.
3. Verified eligible historical outcomes for per-company frequencies and the
   playbook's pooled fallback when company history is under six. Neither the
   single retrospective annual case nor pending targets supply those frequencies.
4. Resolution or explicit conservative handling of the six release-date gaps,
   timezone/clock precision and call-versus-publication distinctions. Date-only
   evidence cannot justify a fabricated release timestamp. Lock timing must use
   an agreed earliest-possible publication boundary, not the later call time.
5. Result-basis review for Salesforce/Okta/SentinelOne independently of their
   growth blocks, and comparable fiscal-week/source-period selection for all.
6. Session 3's database-enforced immutable ledger, exact input/guidance snapshots,
   UTC creation timestamps, duplicate prevention, announcement evidence,
   append-only outcomes and tested Brier scoring. These are **not implemented**.

This preparation pass stops for review. No prediction was locked, probability
published or historical annual evaluation presented as a live track record.


## Verification results

- Python: **335 passed, 3 pre-existing uncached-filing skips**.
- Frontend: **23 passed**; TypeScript, ESLint and Webpack production build pass.
- Direct HTTP: all ten companies in default-off and explicit opt-in modes;
  quarterly calculations/evidence and blocked states remain available. Unsupported
  MSFT, invalid dates and an unpublished cutoff retain honest states.
- Existing deal-page text control: four representative routes returned 200 and
  identical text in both flag modes. Main-versus-earnings visual comparison and
  screenshots remain **unverified/not produced**.
- Static CSS: unchanged global source, zero changed/removed existing declaration
  keys under the canonical compiler. This does not close the visual gate.

Current main advanced during the review only in protected Python deals files;
the final source/CSS check was refreshed against the revision shown above. No
protected files or main working-tree contents were edited. No prediction or
manual date confirmation was recorded. Stop for review before Session 3.
