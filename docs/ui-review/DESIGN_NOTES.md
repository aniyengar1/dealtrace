# DealTrace UI Redesign — Design Notes

Branch: `ui-redesign` in `~/dealtrace-ui` (worktree off `main`, not merged/pushed). Dev server: `npm run dev -- -p 3001` in `apps/web`, running at **http://localhost:3001**.

## Round 3 — imagery visible through the whole page, brighter photos

Round 2 kept the montage `fixed` (good) but then blanketed every section below the hero in a `bg-bg/80 backdrop-blur-sm` panel, which made it read as "plain black below the hero" exactly as flagged. Fix was architectural, not just a number tweak:

- **Removed the full-section panels entirely.** Sections are transparent now; the montage shows fully in the gaps between content.
- **Local contrast only where text sits**, two flavors depending on what's already there:
  - Where text already sat on an opaque `Card` (pipeline steps, featured deal cards, credibility cards, methodology's tables/lists) — nothing to change, those were already "local panels" by construction.
  - Where text sat directly on the page background (every `SectionHeading`, `StatNumber`, and a few standalone links/paragraphs) — added a `bg-bg/55 backdrop-blur-sm` panel sized to the text itself (`inline-block`, not full section width) via `SectionHeading.tsx` and `StatNumber.tsx` directly, so every call site got it for free.
  - The hero headline gets its own local **radial gradient** (not a box) behind the text column specifically, strong at the text and fading to nothing by the time it reaches the histogram card's side of the hero — stronger contrast exactly where the biggest, most important text is, without darkening the rest of the hero.
- **Lightened `HeroMedia`'s shared overlay** roughly in half (diagonal layer: 0.92/0.85/0.68/0.82 → 0.5/0.4/0.25/0.38; vertical layer: 0.20→0.70→solid → 0.05→0.22→0.38) since it now only has to carry general legibility, not the hero by itself.
- **Brightened the footage**: `filter: brightness(1.2) contrast(1.05)` on the actual `<video>`/`<img>` elements (and the static poster, for the reduced-motion/first-paint case) — applied to the media layer only, never the overlay or any text, so brightening the montage can't touch headline crispness.

Visually verified every section on `/` and `/methodology` after this change: imagery (NYC skyline, boardroom interiors, Central Park) is clearly visible and bright behind every section, every panel of text stays crisp, hero headline is unaffected. Didn't touch the `isMobile`/`prefersReducedMotion` branching in `HeroMedia.tsx` at all this round — only the shared overlay/filter values that apply uniformly regardless of device — so those fallbacks are unchanged by construction, not just by re-test.

One unrelated hazard hit mid-verification: the dev server OOM-crashed (`JavaScript heap out of memory`), almost certainly from a stray browser tab stuck repeatedly hitting `/stats` (which does a full per-deal DB fan-out) combined with a long HMR session. Restarted cleanly; not a regression from this round's code.

## Round 2 — black/silver palette, persistent background, verified data accuracy

### Palette
Replaced the navy/gold theme with monochrome black/silver, same token structure: `--color-bg` (#0a0a0b), `--color-surface` (#111214), `--color-surface-raised` (#1a1b1e), `--color-border`/`-strong` (#2a2b2e / #3d3f44), `--color-ink` (#f2f2f3), `--color-ink-muted` (#8b8e94), `--color-ink-faint` (#56585d), `--color-accent` (#c0c4cc) + `--color-accent-bright` (#e5e7eb) replacing gold everywhere (`gold`→`accent` renamed across ~20 files). Chart series (`--color-chart-1..6`) are now a white→dark-silver ramp instead of the old blue/teal/violet/coral palette — bidders on the bid chart and timeline categories are now distinguished by value, not hue. Kept `--color-positive`/`--color-negative` (muted green/red) for bump-direction and review-status semantics — these are functional indicators, not brand accent, so they stay outside the "one accent" rule.

### Persistent background
`HeroMedia` is now `position: fixed` (was `absolute`, scoped to the hero section) and rendered as a sibling at the top of the page, not nested inside the hero `<section>` — `position: fixed` escapes normal document flow entirely, so it keeps covering the full viewport as the page scrolls, which is what makes it read as a backdrop behind every section instead of just the hero. Mounted on `/` and `/methodology` only; data pages never render it. Every section below the hero sits on a `bg-bg/80 backdrop-blur-sm` panel (methodology wraps its whole content in one such panel, since it reads as a single long-form document rather than distinct alternating sections like home). The hero's own overlay gradient was darkened (0.92/0.85/0.68/0.82 steps, up from the navy version's 0.88/0.8/0.6/0.75) since the montage now includes daylight boardroom/park photos, which need more darkening than night skylines to hold AA contrast.

### New photos mixed into the montage
Added 4 verified-free Unsplash photos (`hero-photo-5..8`: Benjamin Child's conference table, Bennie Bates' conference room, David Vives' glass building, Amelia's park) to the existing 4 night-skyline photos + 3 Mixkit clips, for an 11-slide loop that alternates video → boardroom → skyline-photo → video → boardroom → skyline-photo → video → Manhattan building → park → skyline → skyline. Mobile still gets the 8-photo-only path (no video). All sourcing is in `apps/web/public/CREDITS.md` and credited in the footer.

### Ticker
Slowed from 50s to 75s per full loop (your 60–90s target; the literal "3–4x" framing was likely driven by how crowded the *unfiltered* ticker was before the accuracy fix below, not the raw duration). Pause-on-hover needed a real fix, not just a Tailwind class: `group-hover:[animation-play-state:paused]` lives in Tailwind's `@layer utilities`, which CSS always ranks *below* unlayered rules regardless of specificity or source order — so it silently lost to the plain `.animate-ticker { animation: ... }` rule in the same file. Fixed with an explicit unlayered `.group:hover .animate-ticker { animation-play-state: paused }` rule. Verified via `getComputedStyle(...).animationPlayState` before/after (`"running"` → `"paused"`), not just visually, since a screenshot diff alone couldn't distinguish "paused" from "very slow."

### Data accuracy (the main point of this round)
The hero histogram and headline count now come from **canonical deals only** (`deals.is_canonical`), matching `src/bulk_stats.py`'s exact definitions and exclusion thresholds — not read from `data/output/stats/headline_stats.json` directly, but a from-scratch TypeScript port (`src/lib/entityMatch.ts`, `src/lib/canonicalStats.ts`) verified against a real snapshot of that file:
- `n_canonical_deals`: **964** — exact match.
- `pct_increase_cash_deals`: **n=353**, min/median/max all exact matches (-85.37 / 9.52 / 296.83). This is the number that used to show as 847 (all deals, no cash/exclusion filtering) then 353 after switching to the right definition.
- `bidders_who_submitted_a_proposal`: median **2**, max **43** — exact match, but only after porting `entity_match.py`'s `core_name`/`is_same_entity`/`is_acronym_of`/`resolveTarget` (a naive proposer≠target string check alone gave median 3, not 2 — plenty of "distinct bidders" were really the target company under an informal name or acronym).
- `proposals_per_deal`: median **7** — exact match.
- `days_first_contact_to_signing`: **n=948**, median **290.5**, and the exclusion counts matched exactly too (2 no-start, 13 no-signing, 1 negative-duration).

**Why port the logic instead of reading the file** (you said "ideally read it directly"): `headline_stats.json` lives in `~/dealtrace/data/output/stats/`, gitignored and outside this worktree entirely (a separate git worktree of the same repo). It also only carries summary statistics (n, min/p25/median/p75/max, top-10 outliers) — not the full 353-value array the histogram needs to bucket. Reading it would mean (a) a fragile cross-worktree filesystem dependency that breaks on any other machine/deployment, and (b) still needing to recompute the histogram from the DB anyway. Given I had to replicate the per-deal logic regardless, doing it for all five stats and verifying exact parity seemed more robust than a partial file-read. If you'd still prefer the literal file read (e.g. for provenance/freshness display), it's a small addition on top of what's here — ask and I'll add it.

Also fixed **the ticker**: now filters to `is_canonical` deals with a real, resolved acquirer — excluding generic placeholders (`unknown`/`parent`/`merger sub`/`acquiror`/`buyer`/`consortium`/`sponsor`, matching `dedup_deals.py`'s own exclusion set), anonymized filing labels (`Company A`, `Party B`), anything containing "committee", and the target appearing as its own acquirer (entity-matched, not just exact string equality). Curated (non-`bulk_`-slug) deals sort first since those are the well-known ones.

### New files
`src/lib/entityMatch.ts` (port of `entity_match.py`), `src/lib/canonicalStats.ts` (port of `bulk_stats.py`'s five headline stats), `src/lib/tickerDeals.ts` (ticker filtering). `homeStats.ts` was rewritten to call `canonicalStats.ts` instead of the old all-deals DB fan-out — as a side effect, the home page also got faster (~2.3s → ~1.4s warm), since it's now 3 bulk queries instead of one SQL call per deal.

### Verification
`npx tsc --noEmit`, `npx eslint .`, `npx vitest run` (47/47) all clean. Visually checked `/`, `/methodology`, `/deals`, `/deals/splunk`, `/stats` at 1440px; confirmed via DOM/computed-style inspection (not just screenshots) that the ticker pause and the canonical-stat numbers are actually correct, not just visually plausible.

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
