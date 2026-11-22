-- DRAFT -- NOT YET RUN ANYWHERE. Owner-run only, in the Supabase SQL
-- editor, after supabase/readonly_role.sql has already created the
-- dealtrace_web role for the main deals site.
--
-- Creates ONLY the tables the public Crosscheck routes actually read,
-- scoped to dealtrace_web, with everything else (anon, authenticated)
-- explicitly revoked. This is a minimal alternative to running the
-- full db/migrations/0100-0107 sequence: it deliberately does NOT
-- create earnings_live_predictions, earnings_live_results,
-- earnings_historical_observations, or any other live-ledger/pipeline
-- -internal table (hurdle_calculations, hurdle_input_edges,
-- guidance_outcomes, earnings_metric_facts, earnings_quarter_outcomes,
-- earnings_actual_edges) -- none of those are queried by any public
-- route; see the investigation this file came out of for the
-- route-by-route trace.
--
-- Scope, by route:
--   /crosscheck, /crosscheck/[ticker], /api/crosscheck/[ticker]
--     -> companies, earnings_company_reports, earnings_quarter_calculations,
--        guidance_versions, earnings_actuals (via apps/web/src/lib/crosscheck/
--        queries.ts, over the shared DATABASE_URL pool / dealtrace_web role --
--        the SAME role and connection the deals site uses, not a separate one)
--   /crosscheck/predictions, its methodology page
--     -> crosscheck_prediction_snapshots, crosscheck_backtest_snapshots
--        (via apps/web/src/lib/crosscheck/predictions/read.ts, over a
--        SEPARATE CROSSCHECK_PUBLISHED_DATABASE_URL connection -- also
--        the dealtrace_web role, just a different env var/connection string
--        pointed at the same database)
--
-- If you instead run the full db/migrations/0100-0107 sequence (e.g.
-- because you also need the Python pipeline's write path, or the
-- live-ledger tables for internal use), this file is NOT needed for
-- the companies/reports/quarters tables -- those migrations already
-- create them. You'd still need this file's dealtrace_web GRANT/RLS
-- block for THOSE tables (copy it over), since 0100-0102 only grant
-- anon/authenticated/service_role, never dealtrace_web, and you'd
-- still skip creating the live-ledger tables' grants for dealtrace_web
-- the same way (0103 already never grants them to dealtrace_web
-- either -- only anon/authenticated/service_role -- so no action is
-- needed there either way).
BEGIN;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dealtrace_web') THEN
    RAISE EXCEPTION 'dealtrace_web role does not exist -- run supabase/readonly_role.sql first';
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Product tables (companies / reports / quarters) -- matches
-- db/migrations/0100_crosscheck.sql, 0101_crosscheck_product.sql, and
-- 0102_crosscheck_quarters.sql column-for-column, with ONE deliberate
-- difference: earnings_company_reports.hurdle_id drops its FOREIGN KEY
-- to hurdle_calculations, because hurdle_calculations is a pipeline
-- -internal table this file never creates (its result is already
-- denormalized into earnings_company_reports.payload, which is all any
-- public route ever reads). The column itself (and the data in it) is
-- unaffected -- only the referential-integrity check is gone.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.companies (
    id UUID PRIMARY KEY,
    ticker TEXT NOT NULL UNIQUE,
    cik TEXT NOT NULL UNIQUE CHECK (cik ~ '^[0-9]{10}$'),
    name TEXT NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.earnings_actuals (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES public.companies(id),
    content_hash TEXT NOT NULL UNIQUE,
    concept TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL CHECK (period_end >= period_start),
    value NUMERIC NOT NULL,
    unit TEXT NOT NULL,
    basis TEXT NOT NULL,
    accession TEXT NOT NULL,
    filed_date DATE NOT NULL,
    form TEXT NOT NULL,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    source_url TEXT NOT NULL,
    derivation TEXT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id, company_id)
);
CREATE INDEX IF NOT EXISTS earnings_actuals_asof_idx ON public.earnings_actuals (company_id, filed_date, period_start, period_end);

CREATE TABLE IF NOT EXISTS public.guidance_versions (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES public.companies(id),
    content_hash TEXT NOT NULL UNIQUE,
    issued_start DATE NOT NULL,
    issued_end DATE NOT NULL CHECK (issued_end >= issued_start),
    issued_precision TEXT NOT NULL CHECK (issued_precision IN ('day', 'month', 'range')),
    filed_date DATE NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL CHECK (period_end >= period_start),
    metric TEXT NOT NULL,
    low NUMERIC,
    high NUMERIC,
    currency TEXT NOT NULL,
    basis TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('initial', 'reaffirmed', 'raised', 'lowered', 'withdrawn', 'reinstated')),
    accession TEXT NOT NULL,
    exhibit TEXT NOT NULL,
    source_url TEXT NOT NULL,
    quote TEXT NOT NULL CHECK (length(trim(quote)) > 0),
    original_verified BOOLEAN NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((status = 'withdrawn' AND low IS NULL AND high IS NULL) OR
           (status <> 'withdrawn' AND low IS NOT NULL AND high IS NOT NULL AND low <= high)),
    CHECK (NOT original_verified OR status = 'initial'),
    CHECK (issued_precision <> 'day' OR issued_start = issued_end),
    UNIQUE (id, company_id)
);
CREATE INDEX IF NOT EXISTS guidance_versions_asof_idx ON public.guidance_versions (company_id, filed_date, issued_end);

CREATE TABLE IF NOT EXISTS public.earnings_company_reports (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES public.companies(id),
    as_of DATE NOT NULL,
    report_version TEXT NOT NULL,
    hurdle_id UUID NOT NULL, -- no FK to hurdle_calculations here -- see header comment
    forecast_id UUID NOT NULL,
    forecast_method TEXT NOT NULL,
    forecast_estimate NUMERIC,
    benchmark_estimate NUMERIC,
    forecast_status TEXT NOT NULL CHECK (forecast_status IN ('experimental', 'blocked')),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS earnings_reports_lookup ON public.earnings_company_reports (company_id, as_of DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS public.earnings_quarter_calculations (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES public.companies(id),
    as_of DATE NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL CHECK (period_end >= period_start),
    formula_version TEXT NOT NULL,
    policy JSONB NOT NULL,
    guidance_id UUID,
    prior_quarter_id UUID,
    state TEXT NOT NULL CHECK (state IN ('ok', 'blocked')),
    reason_codes TEXT[] NOT NULL,
    guidance_low NUMERIC,
    guidance_high NUMERIC,
    growth_low NUMERIC,
    growth_high NUMERIC,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (guidance_id, company_id) REFERENCES public.guidance_versions (id, company_id),
    FOREIGN KEY (prior_quarter_id, company_id) REFERENCES public.earnings_actuals (id, company_id)
);
CREATE INDEX IF NOT EXISTS earnings_quarter_calculations_asof_idx ON public.earnings_quarter_calculations (company_id, as_of, period_start, period_end);

-- ---------------------------------------------------------------------------
-- Published prediction snapshots -- matches earnings/sql/published_snapshots.sql
-- exactly (same CHECK constraints, same RLS/grant shape). If that file
-- has already been run against this database, these CREATE TABLE IF
-- NOT EXISTS statements are no-ops and the GRANT/POLICY statements
-- below are simply redundant (idempotent), not conflicting.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.crosscheck_prediction_snapshots (
    snapshot_id TEXT PRIMARY KEY CHECK (snapshot_id = 'current'),
    published_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    payload JSONB NOT NULL CHECK ((payload ->> 'schema_version') IS NOT DISTINCT FROM 'crosscheck-public-predictions-v1')
);

CREATE TABLE IF NOT EXISTS public.crosscheck_backtest_snapshots (
    snapshot_id TEXT PRIMARY KEY CHECK (snapshot_id = 'current'),
    published_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    payload JSONB NOT NULL CHECK ((payload ->> 'kind') IS NOT DISTINCT FROM 'BACKTEST_PUBLIC_DATE_RECONSTRUCTION_NOT_LIVE')
);

-- ---------------------------------------------------------------------------
-- RLS + grants: dealtrace_web SELECT-only on exactly these 7 tables,
-- anon/authenticated/service_role explicitly revoked (not just left
-- ungranted -- Supabase's default ACLs can hand these roles table
-- privileges on their own, and TRUNCATE in particular isn't gated by
-- RLS at all, so an explicit REVOKE matters even though the original
-- 0100-0102 migrations never grant dealtrace_web anything to begin
-- with). FORCE ROW LEVEL SECURITY so even this script's own owner
-- role can't read around the policy by accident.
-- ---------------------------------------------------------------------------

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'companies', 'earnings_actuals', 'guidance_versions',
        'earnings_company_reports', 'earnings_quarter_calculations',
        'crosscheck_prediction_snapshots', 'crosscheck_backtest_snapshots'
    ] LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', t);

        DECLARE
            r TEXT;
        BEGIN
            FOREACH r IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
                    EXECUTE format('REVOKE ALL ON public.%I FROM %I', t, r);
                END IF;
            END LOOP;
        END;

        EXECUTE format('GRANT SELECT ON public.%I TO dealtrace_web', t);
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_dealtrace_web_read', t);
        EXECUTE format('CREATE POLICY %I ON public.%I FOR SELECT TO dealtrace_web USING (true)', t || '_dealtrace_web_read', t);
    END LOOP;
END $$;

GRANT USAGE ON SCHEMA public TO dealtrace_web;

COMMIT;
