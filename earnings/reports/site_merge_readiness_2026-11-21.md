# Earnings merge preparation — November 21, 2026

No merge was performed. This review inspected only git objects in the earnings worktree, not the deals checkout. Inspected main: `06dc7592dbc8ae3d27276f245b7c02b67aebd2d7`; common ancestor: `66bd98c89121b05cc2d9dbd921a756a95d4b082f`. The UI-redesign branch is not assumed final or pushed. No remote fetch, push or deployment occurred.

## Tailwind loader

The requested narrowing is already on earnings, introduced in `be2e798`: `next.config.ts` runs the custom Tailwind loader on **`globals.css` only**, not `*.css` or CSS modules. Next retains native CSS-module identity/class exports. No redundant configuration change was needed. New regression tests enforce the narrow rule, the unchanged default `next build` script, and standard PostCSS support. The tests do not force Webpack for deployment.

## Conflict and integration review

Against the inspected main ref, **0 frontend paths were changed on both branches since the common ancestor**. This is a read-only file-overlap check, not a guarantee from executing a merge. Future commits/UI-redesign changes can add conflicts; no main merge was attempted.

The shared earnings differences most likely to require coordination or resolution when the redesign lands are:

- `apps/web/src/components/layout/NavBar.tsx`: preserve the Crosscheck link in the redesigned desktop/mobile navigation.
- `apps/web/next.config.ts`: retain global-only Tailwind loading; do not restore the CSS-module-breaking wildcard.
- `apps/web/postcss.config.mjs`: standard Tailwind PostCSS plugin; reconcile any redesign-specific pipeline.
- `apps/web/package.json`: keep the pinned PostCSS dependency and default build command.
- `apps/web/package-lock.json`: reconcile dependency/lock changes consistently.

Current main has incoming-only updates to layout, global CSS, HeroMedia and deal views; these are design/contract review points, not demonstrated text conflicts. Retain the redesign's shared components/styles when an owner later authorizes the merge, then recheck Crosscheck layout, background, CSS-module delivery and snapshot-only data access. Visual compatibility remains unverified. A complete machine-readable branch file inventory is in [validation](../validation/merge_readiness_2026-11-21.json).

## Checks

- Typecheck: `./node_modules/.bin/tsc --noEmit` — passed.
- Lint: `npm run lint` — passed.
- Frontend: `npm test` — **69 passed across9 files**, including loader-narrowing tests.
- Production build: `npm run build -- --webpack` — passed compilation, TypeScript, static generation and route generation.
- Bootstrap/walk-forward Python tests: **14 passed**, with `DATABASE_URL=''` to prevent the repository's autouse migration fixture from connecting to the live database.

Default Turbopack was not retried or relabelled passed in this task; its previous managed-worker-port permission blocker remains documented in [the prior build review](backtest_build_followup_2026-11-21.md). The requested Webpack verification passed, and the default build script is unchanged.

## Significance result and safeguards

The first task is committed as `b773d93`. On108 company-specific predictions across64 companies, mean Smoothed-minus-pooled Brier is **−0.08345**; the paired company-cluster percentile interval is **[−0.16700,+0.00402]** (95%,10,000 resamples, seed20261121), **including zero**. It preserves whole paired clusters and targets the quarter-weighted mean. Cross-company dependence and selected retrospective data remain limitations. Method, cluster sizes, input/draw/distribution hashes and the honest sentence are in [the backtest report](backtest_walkforward.md) and publication summary.

MongoDB/Firebolt close and consolidation-date evidence is an unchecked owner TODO in `CURRENT_CHECKS.md`, not an invented date or new comparability decision. All532 original case inputs/probabilities/scores, original means and published prediction JSON are unchanged. No live database connection, ledger write, lock, backdating, tag movement or production promotion occurred. The updated snapshot seed is an owner-run file and was not applied. Four pre-existing announcement edits remain unstaged.
