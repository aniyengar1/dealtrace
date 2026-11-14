# DealTrace UI Redesign — Design Notes

Branch: `ui-redesign` in `~/dealtrace-ui` (worktree off `main`, not merged/pushed). Dev server: `npm run dev -- -p 3001` in `apps/web`, running at **http://localhost:3001**.

## Pages to review

- `/` — home
- `/deals` — deal explorer (search/filter/sort/paginate; try `?q=splunk`)
- `/deals/splunk`, `/deals/zendesk`, `/deals/activision` — deal pages (showpiece)
- `/methodology`
- `/stats`, `/deals/splunk/memo`, `/review/splunk` — restyled, behavior unchanged

## Design tokens

Defined as CSS variables in `apps/web/src/app/globals.css` via Tailwind v4's `@theme`:

- **Background/surfaces**: `--color-bg` (#070b1f), `--color-surface` (#0e1330), `--color-surface-raised` (#141a3d)
- **Borders**: `--color-border` (#232a52), `--color-border-strong` (#333c6e)
- **Text**: `--color-ink` (#eef0f8, off-white), `--color-ink-muted` (#97a0c3), `--color-ink-faint` (#5c6490)
- **Accent**: `--color-gold` (#c9a44c) — used sparingly for key numbers, active states, links, primary buttons
- **Chart palette** (category/series color only, never UI chrome): `--color-chart-1..6`, blues/teals/violets/corals, deliberately distinct from gold
- **Semantic**: `--color-positive` / `--color-negative` for bump direction, review status
- Radii: `--radius-sm/md/lg` (4/6/10px)

## Typography

`next/font/google` in `apps/web/src/app/layout.tsx`:
- **Fraunces** (`--font-fraunces`) — display serif for all headlines (h1/h2, stat numbers)
- **Inter** (`--font-sans`) — UI/body
- `font-feature-settings: "tnum" 1` on `body` gives tabular numerals everywhere by default

## Key decisions

- **Hero chart is a histogram, not a per-deal list.** The brief suggested "distribution of % increase from first proposal to final price." Built as `HeroBumpChart` (bucketed bars, open-ended top/bottom buckets) rather than one bar per deal — the dataset is live and growing (see below), so a fixed per-deal chart would become unreadable and would let a single outlier distort the visual. A histogram absorbs outliers into its top bucket gracefully.
- **"Median parties contacted" → "median distinct bidders."** The literal "every named party mentioned in an event" proxy (advisors, law firms, individual directors) produced a misleadingly high number (~26 median) that doesn't mean "potential buyers canvassed." Swapped for `nBidders` — already a tested, reused metric from `crossDealStats.ts` / the existing `/stats` page — which is the honest, defensible number.
- **Horizontal timeline is additive, not a replacement.** Added `HorizontalTimeline.tsx` (time-proportional, color-coded by a 6-category grouping of the ~20 `event_type` values, scrollable) above the existing vertical filterable event list, which stays for dense readability on deals with 50–100+ events. Round separators live on the bid chart only (rounds are fundamentally a bidding concept per `rounds.ts`'s own docstring, not a raw-event one) — didn't duplicate that logic onto the timeline.
- **Parties panel is derived, not hand-mapped.** Lists every name from events/proposals grouped into Target / Acquirer / Other bidder / Mentioned party, computed from the data itself — no hardcoded advisor/role map, since that isn't extracted.
- **Deal Explorer loads all deals per request** (reusing `computeDealStatsRow`, same approach `/stats` already used) rather than pushing aggregation into SQL. Reuses validated logic instead of re-deriving bidder counts/rounds/bump % in SQL; acceptable at the current data volume (~1,100+ rows and growing — see below), called out here as the thing to revisit if it ever gets slow.
- **Unreviewed-data markers.** A small gold `•` marks any Deal Explorer cell resting on at least one unreviewed fact — same convention `/stats` already used, extended to the new page rather than inventing a second convention.

## The dataset changed size live, mid-build

A separate Claude Code session on `main` was running a bulk extraction/load job the whole time this branch was built. The `deals` table grew from 10 rows to 1,100+ during this session, and kept growing. Two consequences worth knowing about:

1. **This is why the hero chart is a histogram and "parties contacted" got redefined** — both decisions above were direct responses to what showed up once real bulk data (not just the 10 hand-curated gold deals) hit the page.
2. **Observed a real data-quality issue, not a UI bug**: the same underlying filing can appear as two separately tracked `deals` rows (e.g. `splunk` and `bulk_1353283_000114036123050211`, same Cisco/Splunk filing) before de-duplication catches up on the loading side. Not something this branch fixes (out of scope — it's pipeline/`src/` territory per the isolation instructions) but documented as a known limitation on `/methodology` and worth a look on the `main` side.

## What I couldn't do / didn't do, and why

- **Screenshots were not saved to `docs/ui-review/`.** The only browser automation available to me drives your actual Chrome browser (a separate host context from this sandbox), not a headless one I can write files from. Saving real PNGs would have required installing Playwright as a devDependency in `apps/web`; I asked, and you said to skip it. All pages were reviewed live instead (desktop 1440px and mobile 390px) — see the page list above to re-check them yourself in-browser.
- **Deal value / market cap is not shown** anywhere (home stats, Deal Explorer). The schema only ever captures *price per share*, never shares outstanding or aggregate transaction value, so this is hidden rather than approximated.
- **"Size bucket" filter on `/deals`** is a price-per-share bucket (Under $20 / $20–50 / $50–100 / $100+), not a market-cap bucket, for the same reason. Labeled accordingly, not as "size."
- **SEC filing links are best-effort.** `deals` has no filing reference of its own (it's a hand-registered table, independent of the automated `deal_candidates` discovery table), so `getFilingUrlForDeal` fuzzy-joins on `target_name ILIKE search_term`. Falls back to hiding the link rather than guessing when there's no confident match.
- **20-deal spot-check row on `/methodology`'s accuracy table** is marked "Pending" (not a number) since that work hasn't happened yet.

## Shared files touched (for the `earnings` branch merge)

Per the isolation instructions, the `earnings` branch also edits `apps/web/src/app/layout.tsx`, `package.json`, `package-lock.json`, and `postcss.config.mjs`. Status on this branch:

- **`apps/web/src/app/layout.tsx` — touched, substantially.** Unavoidable: the brief required a new global nav/footer, fonts, and metadata, which all live here. `earnings`'s only change to this file was adding one `<Link href="/crosscheck">` inside the old `<nav>`. That nav markup is gone (replaced by `NavBar.tsx`), so the merge will need to manually re-add a "Crosscheck" link into `src/components/layout/NavBar.tsx`'s `LINKS` array — a one-line addition, not a conflict in substance.
- **`package.json` / `package-lock.json` — untouched.** No new runtime dependencies were added; everything is built on what was already in `package.json` (Next's built-in `next/font` and `next/og`, no charting library, no Tailwind config file needed beyond the existing `@tailwindcss/turbopack` setup).
- **`postcss.config.mjs` — untouched / does not exist on this branch.** `earnings` added one to wire up `@tailwindcss/postcss` for the Webpack fallback; this branch only ever ran via Turbopack dev (`next.config.ts`'s existing `turbopack.rules` block), so it was never needed here. Whoever merges should keep `earnings`'s version if the production build needs the Webpack path.

## Verification

- `npx tsc --noEmit` — clean
- `npx eslint .` — clean
- `npx vitest run` — 47/47 passing (no existing test was touched in a way that changed its assertions; `crossDealStats.ts` gained new fields but no existing field was removed or renamed)
- Dev server running on port 3001 throughout; every route above was loaded and visually checked at both 1440px and 390px widths.
