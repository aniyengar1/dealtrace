-- Read-only Postgres role for apps/web in production (Vercel -> Supabase
-- transaction pooler). Grants SELECT only on the 10 DealTrace tables --
-- no INSERT/UPDATE/DELETE, and no access to anything outside this list
-- (in particular, never the earnings/Crosscheck tables, which this role
-- is never granted on at all).
--
-- Run this yourself in the Supabase SQL editor, replacing the password
-- placeholder with your own before running (or edit it in after, via
-- ALTER ROLE dealtrace_web WITH PASSWORD '...').
--
-- Safe to re-run: every statement is idempotent.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dealtrace_web') THEN
        CREATE ROLE dealtrace_web WITH LOGIN PASSWORD '<SET_IN_SQL_EDITOR>';
    END IF;
END $$;

-- Supabase's default database is named "postgres" -- confirm with
-- `SELECT current_database();` in the SQL editor if this project's
-- differs, and change the name below to match.
GRANT CONNECT ON DATABASE postgres TO dealtrace_web;
GRANT USAGE ON SCHEMA public TO dealtrace_web;

GRANT SELECT ON TABLE
    public.deals,
    public.paragraphs,
    public.extraction_runs,
    public.events,
    public.proposals,
    public.valuations,
    public.deal_candidates,
    public.deal_metrics,
    public.headline_stats,
    public.schema_migrations
TO dealtrace_web;

-- No ALTER DEFAULT PRIVILEGES grant here on purpose: new tables created
-- later are NOT automatically readable by this role. Re-run (or extend)
-- this script explicitly when the 10-table scope changes.

-- Building the transaction-pooler URL for this role:
-- Open the Supabase dashboard's Connect page and copy the "Transaction
-- pooler" connection string shown there (host something like
-- aws-0-<region>.pooler.supabase.com, port 6543, dbname postgres) --
-- then swap only the username and password: the username becomes
-- "dealtrace_web.<project-ref>" (Supavisor's pooler routes by appending
-- the project ref to whichever role name you log in as, same as the
-- default postgres.<project-ref> form shown in the dashboard), and the
-- password is the one you set for dealtrace_web above. Everything else
-- in the dashboard's string (host, port, dbname, sslmode) stays as-is.
