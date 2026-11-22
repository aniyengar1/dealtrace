-- OWNER-RUN ONLY. No live-ledger reads/writes; no views over live tables.
-- Run as a database administrator in the intended Supabase project.
BEGIN;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dealtrace_web') THEN
    CREATE ROLE dealtrace_web NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='dealtrace_web' AND (rolsuper OR rolbypassrls)) THEN
    RAISE EXCEPTION 'dealtrace_web must be an ordinary non-BYPASSRLS role';
  END IF;
END $$;
CREATE TABLE IF NOT EXISTS public.crosscheck_prediction_snapshots (
  snapshot_id text PRIMARY KEY CHECK (snapshot_id='current'),
  published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  payload jsonb NOT NULL CHECK ((payload->>'schema_version') IS NOT DISTINCT FROM 'crosscheck-public-predictions-v1')
);
CREATE TABLE IF NOT EXISTS public.crosscheck_backtest_snapshots (
  snapshot_id text PRIMARY KEY CHECK (snapshot_id='current'),
  published_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  payload jsonb NOT NULL CHECK ((payload->>'kind') IS NOT DISTINCT FROM 'BACKTEST_PUBLIC_DATE_RECONSTRUCTION_NOT_LIVE')
);
ALTER TABLE public.crosscheck_prediction_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crosscheck_prediction_snapshots FORCE ROW LEVEL SECURITY;
ALTER TABLE public.crosscheck_backtest_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crosscheck_backtest_snapshots FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.crosscheck_prediction_snapshots,public.crosscheck_backtest_snapshots FROM PUBLIC,dealtrace_web;
-- Supabase default ACLs can grant table privileges to these roles. In
-- particular TRUNCATE is not constrained by RLS, so revoke explicit grants.
DO $$ DECLARE r text; BEGIN
  FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN
      EXECUTE format('REVOKE ALL ON public.crosscheck_prediction_snapshots,public.crosscheck_backtest_snapshots FROM %I',r);
    END IF;
  END LOOP;
END $$;
GRANT USAGE ON SCHEMA public TO dealtrace_web;
GRANT SELECT ON public.crosscheck_prediction_snapshots,public.crosscheck_backtest_snapshots TO dealtrace_web;
DROP POLICY IF EXISTS crosscheck_snapshot_public_read ON public.crosscheck_prediction_snapshots;
CREATE POLICY crosscheck_snapshot_public_read ON public.crosscheck_prediction_snapshots FOR SELECT TO dealtrace_web USING (true);
DROP POLICY IF EXISTS crosscheck_backtest_public_read ON public.crosscheck_backtest_snapshots;
CREATE POLICY crosscheck_backtest_public_read ON public.crosscheck_backtest_snapshots FOR SELECT TO dealtrace_web USING (true);
-- Do not grant this role membership in service_role or privileges on live tables.
-- This script changes grants only on these publication tables, not deals tables.
COMMIT;
