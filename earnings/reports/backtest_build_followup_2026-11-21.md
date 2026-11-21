# Backtest follow-up and default-bundler check — November 21, 2026

## Results

532 unchanged scored targets, 73 companies. Mean unscaled Brier: Raw history 0.4845219366; Smoothed 0.4774861365; **walk-forward pooled base rate 0.5016966940**; uniform 0.6666666667; always-above 0.7593984962. Fitting a frequency vector to all 532 outcomes yields 0.4766521567 **in-sample**, which confirms the owner's rough estimate but uses future labels. It is not the walk-forward benchmark.

| Frozen history selection | n | Raw history | Smoothed | Walk-forward pooled |
|---|---|---|---|---|
| Company-specific | 108 | 0.3950512304 | 0.3901554641 | 0.4736051011 |
| Pooled fallback | 424 | 0.5073116447 | 0.4997307417 | 0.5088520997 |

Smoothed has lower mean loss than the walk-forward pool on this sample. This is a descriptive comparison, not a significance or generalization claim. Subgroups differ in companies and calendar dates; their differences do not establish a causal advantage of company-specific training.

Below-guidance outcomes: **4/532 = 0.7519%**, nominal 95% Wilson interval **0.2928%–1.9171%**. The interval treats quarters as independent and is not company-cluster-adjusted. LULU: 2/7; CNXC: 1/8; PINS: 1/8. The other70 companies have no observed below outcomes. Contemporary two-digit SEC SIC breakdown: apparel products 2/7; business services 2/262; electronic/electrical equipment 0/177; health services 0/14; industrial/computer machinery 0/28; instruments 0/36; miscellaneous retail 0/8. These are not GICS sectors. In particular, cached SEC metadata assigns LULU SIC2300, not a retail code. Small, dependent samples and the survivor-selected guidance-giver cohort limit interpretation.

Full methods, confidence intervals, calibration bins and company counts: [backtest report](backtest_walkforward.md). Exact benchmark input IDs/counts/probabilities are in its JSON companion. Sector source URLs, hashes and original fetch timestamps are pinned in [sector metadata](backtest_sectors.json). No new release bodies or fresh extractor evaluation examples were opened.

## Site and publication

`/crosscheck/predictions` now shows the five-way comparison, company/pool denominators and scores, below rate/interval, and expandable company/industry counts. All new content comes from the published backtest copy. The prediction reader/connection and eight published prediction records are unchanged. Old backtest copies without the comparator fail closed rather than presenting an incomplete comparison.

The generated owner-run `earnings/publication/published_snapshot_seed.sql` is refreshed from the existing prediction copy plus the revised backtest copy. It has not been run against Supabase or the live database. Owner setup remains in `earnings/publication/README.md`.

## Default Turbopack: not yet confirmed passing

Host: Darwin arm64, Node20.20.2, Next16.4.6. `npm run build` invokes **`next build` without a bundler override**, matching main's script. Next16 uses Turbopack by default ([official Next upgrade guide](https://nextjs.org/docs/app/guides/upgrading/version-16)). No bundler, PostCSS, dependency or shared frontend configuration was changed in this follow-up.

Both ordinary and explicitly elevated default-build attempts failed while evaluating the global CSS loader, before successful compilation:

```text
[project]/src/app/globals.css.css [app-client] (css)
creating new process -> binding to a port -> Operation not permitted (os error 1)
```

A separately elevated plain Node ephemeral-port bind succeeded. This narrows the failure to the managed Turbopack worker execution path; it does not prove the application fails in the owner's normal Terminal or in Vercel. A matching [reported parent-versus-worker permission issue](https://github.com/openai/codex/issues/50945) describes the same pattern; that report is corroboration, not proof about this checkout. Do not change production bundlers or CSS to disguise a worker permission failure. **A clean default build on the owner's unrestricted Terminal remains required; no Vercel build was attempted.**

Owner verification command:

```sh
cd ~/dealtrace-earnings/apps/web
npm run build
```

`npm run build -- --webpack` passed compilation, TypeScript, static generation and route output. It is an explicitly requested verification fallback, not a change to the build script or deployment configuration. `tsc --noEmit` also passed. No browser automation was used; visual compatibility remains unverified.

### Existing earnings configuration differences from current main

These date to `be2e798`, before this follow-up:

- `next.config.ts`: custom `@tailwindcss/turbopack` rule narrowed from `*.css` to `globals.css`. Rewriting CSS-module files as ordinary CSS had stripped module exports and left the predictions page unstyled. Main's existing custom loader remains for its global Tailwind entry; native CSS-module handling is retained. Main needs this narrowing when accepting the Crosscheck CSS-module pages, not because its current plain global styles necessarily fail.
- `postcss.config.mjs`: standard Tailwind v4 `@tailwindcss/postcss` plugin.
- `package.json` / lockfile: matching pinned plugin4.3.3. The build script is still `next build`.

The PostCSS plugin follows [Tailwind's official Next integration](https://tailwindcss.com/docs/installation/framework-guides/nextjs) and provides processing for the Webpack path as well. Main's current custom Turbopack loader can process its global entry without this added PostCSS path; it is not established that main requires the plugin simply to run its existing default build. The merged implementation retains it for standard PostCSS/Webpack compatibility. These shared differences still need review before any merge back; main's configuration was not edited.

## Tests and safeguards

- Python targeted offline checks: **32 passed,24 skipped** (DB-backed tests intentionally disabled with `DATABASE_URL=''`). An initial unguarded pytest invocation triggered the repository's migration fixture; its connection was denied before connecting or writing. The corrected run disabled that fixture's database access. No live connection was retried or granted.
- Frontend: **66 passed**. TypeScript: passed. Webpack production build: passed. Default Turbopack: failed with the worker-port error above.
- Exact comparison against `57bd3f9`: **all532 existing case timestamps, selected input IDs, original probabilities and original scores remain unchanged**. Protected prediction code/history/guidance and published prediction JSON remain unchanged; checkpoint tags are not moved.
- No live-ledger writes, locks, backdating, provider calls, push or deployment. Four pre-existing announcement-file edits remain unstaged.

Evidence: [machine-readable checks](../validation/backtest_followup_2026-11-21.json).
