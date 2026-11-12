-- 0008's blanket GRANT ran before this table existed and doesn't apply
-- retroactively, so deal_candidates needs its own grant + policy pair,
-- same pattern as every other table there.
GRANT SELECT ON deal_candidates TO anon, authenticated;
GRANT ALL ON deal_candidates TO service_role;

ALTER TABLE deal_candidates ENABLE ROW LEVEL SECURITY;

CREATE POLICY deal_candidates_select ON deal_candidates FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY deal_candidates_service_all ON deal_candidates FOR ALL TO service_role USING (true) WITH CHECK (true);
