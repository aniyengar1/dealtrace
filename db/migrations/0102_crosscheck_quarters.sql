-- Quarterly guidance shares guidance_versions with a distinct metric and exact
-- period. Annual records/IDs remain intact. No prediction ledger is introduced.
CREATE TABLE earnings_quarter_calculations (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    as_of DATE NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL CHECK(period_end >= period_start),
    formula_version TEXT NOT NULL,
    policy JSONB NOT NULL,
    guidance_id UUID,
    prior_quarter_id UUID,
    state TEXT NOT NULL CHECK(state IN ('ok','blocked')),
    reason_codes TEXT[] NOT NULL,
    guidance_low NUMERIC,
    guidance_high NUMERIC,
    growth_low NUMERIC,
    growth_high NUMERIC,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY(guidance_id,company_id) REFERENCES guidance_versions(id,company_id),
    FOREIGN KEY(prior_quarter_id,company_id) REFERENCES earnings_actuals(id,company_id)
);
CREATE TABLE earnings_quarter_outcomes (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    as_of DATE NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL CHECK(period_end >= period_start),
    guidance_id UUID NOT NULL,
    actual_id UUID NOT NULL,
    classification TEXT CHECK(classification IN ('below','within','above','not_comparable')),
    reason_codes TEXT[] NOT NULL,
    result_issued_start DATE NOT NULL,
    result_issued_end DATE NOT NULL CHECK(result_issued_end >= result_issued_start),
    result_filed_date DATE NOT NULL,
    result_accession TEXT NOT NULL,
    result_source_url TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY(guidance_id,company_id) REFERENCES guidance_versions(id,company_id),
    FOREIGN KEY(actual_id,company_id) REFERENCES earnings_actuals(id,company_id)
);
CREATE INDEX earnings_quarter_calculations_asof_idx ON earnings_quarter_calculations(company_id,as_of,period_start,period_end);
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['earnings_quarter_calculations','earnings_quarter_outcomes'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('GRANT SELECT ON %I TO anon, authenticated', t);
        EXECUTE format('GRANT ALL ON %I TO service_role', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO anon, authenticated USING (true)', t || '_select', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO service_role USING (true) WITH CHECK (true)', t || '_service_all', t);
    END LOOP;
END $$;
