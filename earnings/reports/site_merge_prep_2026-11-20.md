# Crosscheck backtest and site merge preparation — November20,2026

## Backtest

532 scored cases across73 companies;14 source-matched targets lack history. Mean unscaled Brier: raw history 0.4845219365, smoothed 0.4774861364, uniform0.6666666667, always-above0.7593984962. Evaluated outcomes:4 below,198 within,330 above;108 company-history cases and424 pooled. These are retrospective source-curated results, not live validation.

[Method, per-company results and class-specific calibration bins](backtest_walkforward.md). Full case inputs/probabilities/scores are retained in the companion JSON. No backtest is inserted in a live table. The original ten plus63 qualifying scaling issuers form the research pool; the live registry and ten-company pool remain unchanged.

## Merge and shared-file inventory

Merged main@66bd98c89121b05cc2d9dbd921a756a95d4b082f into earnings: first a72c01f, then catch-up50e48ce after the deals agent committed66bd98c. The initial root-layout conflict was resolved by retaining main’s layout. The catch-up includes the data-quality field, warning and migration0020; no live migration was applied. Root layout, global CSS, deal pages and dealMetrics now match merged main byte-for-byte.

Complete retained shared frontend differences versus merged main:

- `apps/web/next.config.ts`
- `apps/web/package-lock.json`
- `apps/web/package.json`
- `apps/web/postcss.config.mjs`
- `apps/web/src/components/layout/NavBar.tsx`

NavBar adds Crosscheck at `/crosscheck/predictions`, retaining `/crosscheck` search/detail routes. Next config retains the CSS-module-safe global loader rule. PostCSS and package/lock files retain the standard Tailwind plugin needed by Webpack. These retained CSS-support changes predate this pass; main’s typography, Card, HeroMedia and global tokens are reused. No global reset/style or root-layout override was added. All incoming main frontend files and module-specific changes are listed in [validation inventory](../validation/site_merge_prep_2026-11-20.json). Coordinate review of these five shared integration differences with the deals agent before any eventual merge back to main. No merge back, push or deployment occurred.

## Published snapshot tables

Route: `/crosscheck/predictions`. The data reader uses only `CROSSCHECK_PUBLISHED_DATABASE_URL`, verifies `dealtrace_web`, starts READ ONLY transactions, and queries a fixed two-table allowlist. It has no live ledger/shared DATABASE_URL fallback. The inherited main layout’s existing deals-metadata query is unchanged. Missing configuration/data fails closed.

Owner-run files (not applied to Supabase):
- [DDL, grants and forced RLS](../sql/published_snapshots.sql).
- [Seed copies of the eight published records and separate BACKTEST summary](../publication/published_snapshot_seed.sql).
- [Setup, refresh and launch instructions](../publication/README.md).

The role has SELECT only; explicit default grants including TRUNCATE are revoked from known Supabase roles. An administrator can replace the publication copy, so this is not an administrator-proof store. Underlying live locks remain immutable. Both methods retain their stored IDs/probabilities/targets/evidence; display labels are Raw history and Smoothed, with explanatory tooltips and at most one decimal for percentages.

## Verification

- Python, including DB-backed tests in a guarded isolated cluster:812 passed,4 skipped,2 preserved xfails. Snapshot SQL integration:3 passed separately. The two xfails are not reported as repaired.
- Mock-only extractor tests had expired-clock assumptions; their test fixture now uses a fixed clock. No production extractor, deadline, budget, cost reservation, prompt, output or fresh evaluation group was changed. No provider calls occurred.
- Frontend:64 passed; Next production build/TypeScript passed using Webpack. Default Turbopack was blocked by worker-port restrictions; no production config was changed to mask that environment issue.
- Direct HTTP (no browser):200, eight prediction records, ten highlighted buckets, backtest, shared navigation, background poster and both stylesheet assets200. Visual/browser compatibility remains explicitly unverified.
- Both-method25-case fixed-input/time regression equals the pre-task reference. All checkpoint tags and protected methods/history/guidance/schema are unchanged.
- READ ONLY live check:8 predictions,0 scores, identical ledger hash and historical inputs. All database-write tests and publication SQL execution were confined to a temporary isolated cluster.

## Lead-time research

[Follow-up report](lead_time_followup_2026-11-20.md): 24/64 complete matching studies,13 newly complete,40 remaining. LITE has a specific Nov5 scheduled versus Nov2 actual mismatch; DOCN/ONTO preliminary disclosures show why a regular-release lead does not establish lock eligibility. All old failure records and financial/backtest input hashes remain preserved. No historical source was relabelled user_verified, and no future date or live record was promoted.

No new locks, backdating, live-ledger writes, fresh-set inference, extractor tuning, push or deployment. Owner review of the integration and manual SQL setup remain outstanding.
