-- Read-only Postgres role for apps/web in production (Vercel -> Supabase
-- transaction pooler). Grants SELECT only on the 9 tables apps/web
-- actually queries -- no INSERT/UPDATE/DELETE, and no access to
-- anything outside this list (in particular, never the earnings/
-- Crosscheck tables, which this role is never granted on at all; and
-- not schema_migrations, which only db/migrate.py reads, never the web
-- app).
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
    public.headline_stats
TO dealtrace_web;

-- Un-does schema_migrations' earlier inclusion in the grant list above,
-- for anyone re-running this script against a database where the prior
-- 10-table version already ran -- REVOKE on a privilege the role never
-- had is a harmless no-op, so this is safe either way.
REVOKE SELECT ON TABLE public.schema_migrations FROM dealtrace_web;

-- No ALTER DEFAULT PRIVILEGES grant here on purpose: new tables created
-- later are NOT automatically readable by this role. Re-run (or extend)
-- this script explicitly when the 9-table scope changes.

-- GRANT SELECT above only controls table-level privilege -- every one
-- of these 9 tables also has row-level security enabled on Supabase,
-- which (unlike the table's owner or a BYPASSRLS role) still hides
-- every row from dealtrace_web unless a policy explicitly admits it.
-- dealtrace_web isn't anon/authenticated/service_role, so the
-- anon/authenticated read policies 0008_rls_policies.sql and
-- 0011_deal_candidates_rls.sql create don't cover it either -- it
-- needs its own. DROP POLICY IF EXISTS first makes each one safe to
-- re-run (e.g. after a fresh push_to_supabase.sh recreates these
-- tables from scratch, wiping any policy that existed on the old
-- table object -- see that script's own warning).
DROP POLICY IF EXISTS dealtrace_web_read ON public.deals;
CREATE POLICY dealtrace_web_read ON public.deals FOR SELECT TO dealtrace_web USING (true);

DROP POLICY IF EXISTS dealtrace_web_read ON public.paragraphs;
CREATE POLICY dealtrace_web_read ON public.paragraphs FOR SELECT TO dealtrace_web USING (true);

DROP POLICY IF EXISTS dealtrace_web_read ON public.extraction_runs;
CREATE POLICY dealtrace_web_read ON public.extraction_runs FOR SELECT TO dealtrace_web USING (true);

DROP POLICY IF EXISTS dealtrace_web_read ON public.events;
CREATE POLICY dealtrace_web_read ON public.events FOR SELECT TO dealtrace_web USING (true);

DROP POLICY IF EXISTS dealtrace_web_read ON public.proposals;
CREATE POLICY dealtrace_web_read ON public.proposals FOR SELECT TO dealtrace_web USING (true);

DROP POLICY IF EXISTS dealtrace_web_read ON public.valuations;
CREATE POLICY dealtrace_web_read ON public.valuations FOR SELECT TO dealtrace_web USING (true);

DROP POLICY IF EXISTS dealtrace_web_read ON public.deal_candidates;
CREATE POLICY dealtrace_web_read ON public.deal_candidates FOR SELECT TO dealtrace_web USING (true);

DROP POLICY IF EXISTS dealtrace_web_read ON public.deal_metrics;
CREATE POLICY dealtrace_web_read ON public.deal_metrics FOR SELECT TO dealtrace_web USING (true);

DROP POLICY IF EXISTS dealtrace_web_read ON public.headline_stats;
CREATE POLICY dealtrace_web_read ON public.headline_stats FOR SELECT TO dealtrace_web USING (true);

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
