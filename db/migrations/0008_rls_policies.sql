-- Supabase provisions `anon`, `authenticated`, `service_role` automatically;
-- a bare local Postgres doesn't have them. Guard their creation so this
-- exact file applies cleanly in both places -- on Supabase the IF NOT
-- EXISTS checks are all true (the real managed roles already exist) and
-- these statements are no-ops; locally they create harmless stand-ins.
--
-- Table owners bypass RLS by default (no FORCE ROW LEVEL SECURITY is set
-- below), so whichever role runs these migrations -- the local superuser
-- today, service_role's underlying owner on Supabase later -- keeps
-- unrestricted read/write regardless of the policies below. These policies
-- only ever restrict non-owner roles connecting as anon/authenticated.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOLOGIN BYPASSRLS;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;

ALTER TABLE deals ENABLE ROW LEVEL SECURITY;
ALTER TABLE paragraphs ENABLE ROW LEVEL SECURITY;
ALTER TABLE extraction_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE valuations ENABLE ROW LEVEL SECURITY;

-- Every deal's data is public-company merger-proxy content, not sensitive
-- per-user data, so a blanket read policy is enough -- there's no
-- multi-tenant/per-user ownership concept to scope rows by. All writes
-- (the loader, future review-status edits) go through service_role; a
-- finer "authenticated can only touch review_status" policy would need a
-- SECURITY DEFINER function (RLS is row-level, not column-level) and is
-- deliberately left for whenever a review UI actually needs it.
CREATE POLICY deals_select ON deals FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY deals_service_all ON deals FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY paragraphs_select ON paragraphs FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY paragraphs_service_all ON paragraphs FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY extraction_runs_select ON extraction_runs FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY extraction_runs_service_all ON extraction_runs FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY events_select ON events FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY events_service_all ON events FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY proposals_select ON proposals FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY proposals_service_all ON proposals FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY valuations_select ON valuations FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY valuations_service_all ON valuations FOR ALL TO service_role USING (true) WITH CHECK (true);
