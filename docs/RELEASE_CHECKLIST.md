# Release checklist

Ordered steps to take the current `main` live. Run everything from the
repo root unless noted. This only covers the deals site plus the
already-public Crosscheck predictions page — `/crosscheck` and
`/crosscheck/[ticker]` stay gated behind `CROSSCHECK_RESEARCH_ENABLED`
(unset in production) until a later release; see the note at the end.

## 0. Local verification (pre-flight)

```
cd apps/web
npx tsc --noEmit
npm run lint
npm run test
npm run build
```

All four should pass clean before touching Supabase or Vercel.

## 1. Push the deals schema + data to Supabase

```
./scripts/push_to_supabase.sh
```

This drops and recreates the 10 deals tables (`deals`, `deal_candidates`,
`deal_metrics` — including the `shares_outstanding`/`aggregate_value`/
`data_quality_flag` columns, already part of the table, nothing extra
to do for those — `extraction_runs`, `events`, `proposals`, `valuations`,
`paragraphs`, `headline_stats`, `schema_migrations`) from your local
Postgres. It prints a row-count table at the end; confirm every row
says `PASS`. **The script's own warning is real: this wipes every GRANT
and RLS policy on those tables**, which is why the next step is not
optional.

## 2. Re-apply `dealtrace_web` grants + RLS for the deals tables

In the Supabase SQL editor, paste and run the full contents of:

```
supabase/readonly_role.sql
```

This creates the `dealtrace_web` role if it doesn't exist yet, grants
it `SELECT` on exactly the 9 tables `apps/web` queries (not
`schema_migrations`), and creates a `dealtrace_web_read` policy on each
so RLS doesn't hide every row from it. Safe to re-run — every statement
is idempotent.

## 3. Publish the Crosscheck prediction snapshots

In the Supabase SQL editor, paste and run the full contents of:

```
earnings/sql/published_snapshots.sql
```

This creates `crosscheck_prediction_snapshots` and
`crosscheck_backtest_snapshots` (if they don't exist), enables and
*forces* RLS on both, revokes any blanket grant `anon`/`authenticated`/
`service_role` might otherwise have on them, and grants `dealtrace_web`
`SELECT` with its own read policy. It does **not** insert any snapshot
data — the tables exist but are empty until you separately publish a
snapshot (see "Publishing snapshot data" below). That's fine:
`/crosscheck/predictions` shows a graceful "No published snapshot is
available" message until you do, not an error.

## 4. Verify

```
./scripts/verify_supabase.sh
```

Confirms the deals-table row counts and three sanity checks (headline
stat medians, the canonical-deal count, the splunk row) match between
local and Supabase. This script does not check the Crosscheck snapshot
tables (they're a separate, dedicated connection — see step 6); if you
want to confirm they're reachable, run a one-off:

```sql
-- as dealtrace_web, e.g. via the Supabase SQL editor's "Run as" role switch
SELECT snapshot_id FROM crosscheck_prediction_snapshots;
SELECT snapshot_id FROM crosscheck_backtest_snapshots;
```

Empty results are expected and fine (no data published yet); an error
means step 3 didn't apply cleanly.

## 5. Vercel environment variables

In the Vercel project settings:

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | Supabase transaction-pooler URL, `dealtrace_web` role | Same one the deals site already uses — confirm it's still correct after step 1's table recreation (the role/password don't change, just re-verify the pooler host if the project ever changed). |
| `SITE_URL` | `https://<your-production-domain>` | Used for sitemap/OG absolute URLs. |
| `CROSSCHECK_PUBLISHED_DATABASE_URL` | **Set** — same Supabase project, same `dealtrace_web` role/password as `DATABASE_URL`, just its own connection string entry | Required for `/crosscheck/predictions` to read the snapshot tables. `apps/web/src/lib/crosscheck/predictions/read.ts` refuses to use any role other than `dealtrace_web` and never falls back to `DATABASE_URL`, so this must be set explicitly even though it points at the same database. |
| `REVIEW_ENABLED` | **Leave unset** | Keeps `/review` 404ing in production. |
| `CROSSCHECK_RESEARCH_ENABLED` | **Leave unset** | Keeps `/crosscheck` and `/crosscheck/[ticker]` 404ing in production — their backing tables (`companies`, `earnings_company_reports`, etc.) haven't been created in Supabase yet. Set this to `true` only after a future release that also runs a schema for those tables (see the note at the end). |

## 6. Push to git

```
git push origin main
```

(This is the one step in this checklist you run, not me — I don't push.)

## 7. Live checks, after Vercel redeploys

- `/` — loads, hero count matches the included-deals total.
- `/deals/splunk` (or any known-good deal) — loads normally.
- `/deals/twitter` — **404** (no completed extraction run).
- A deal with `excluded_from_stats` (e.g. the Viasat/Inmarsat slug) — **404**.
- `/deals`, `/stats` — listings load, counts match `headline_stats`.
- `/deals/export`, `/stats/export` — CSV downloads work.
- A deal page's Open Graph image (share the URL, or hit
  `/deals/splunk/opengraph-image` directly) — renders, not a broken image.
- `/sitemap.xml` — no excluded/no-run deal slugs, no `/crosscheck*` paths
  at all (not even `/crosscheck/predictions` — it isn't in `STATIC_ROUTES`
  today either way).
- `/review` — **404**.
- `/crosscheck` and `/crosscheck/AAPL` (or any ticker) — **404**.
- `/api/crosscheck/AAPL` — **404**.
- `/crosscheck/predictions` — **200**; shows either real locked
  predictions (if you've published a snapshot) or the "No published
  snapshot is available" message (if you haven't yet) — either is
  correct, a 500 or 503 is not.
- `/crosscheck/predictions/methodology` — **200**, always static.

## Publishing snapshot data (separate from this release, repeatable)

Once step 3's schema exists, actually populating
`crosscheck_prediction_snapshots`/`crosscheck_backtest_snapshots` with
real content is its own, independently-repeatable step — not part of
standing up the release. Whatever process produces
`earnings/publication/published_snapshot_seed.sql` (or an updated
version of it) is what you'd paste into the Supabase SQL editor for
that, each time you want to refresh what `/crosscheck/predictions`
shows. Not covered further here since it's a data operation, not a
schema/release one.

## Later: enabling `/crosscheck` and `/crosscheck/[ticker]`

Those two routes (and the API route behind them) need
`companies`/`earnings_company_reports`/`earnings_quarter_calculations`/
`guidance_versions`/`earnings_actuals` to exist in Supabase with
`dealtrace_web` granted on them, which this checklist deliberately
does not set up yet. When you're ready:

1. Either run the full `db/migrations/0100_crosscheck.sql` through
   `0107_crosscheck_entry_window.sql` sequence (if you also want the
   Python pipeline's write path / live-ledger tables for internal use,
   then separately grant `dealtrace_web` on the 5 read-only tables —
   those migrations only grant `anon`/`authenticated`/`service_role`),
   **or** run `supabase/crosscheck_public.sql` on its own (a minimal,
   draft schema covering only those 5 tables plus the two snapshot
   tables, with `dealtrace_web` already granted and RLS'd, and the
   three live-ledger tables never created at all).
2. Set `CROSSCHECK_RESEARCH_ENABLED=true` in Vercel.
3. Re-run the live checks above for `/crosscheck` and `/crosscheck/[ticker]`,
   expecting 200s instead of 404s.
