-- Crosscheck uses separate, namespaced financial records; existing deals tables are untouched.
CREATE TABLE companies (
    id UUID PRIMARY KEY,
    ticker TEXT NOT NULL UNIQUE,
    cik TEXT NOT NULL UNIQUE CHECK (cik ~ '^[0-9]{10}$'),
    name TEXT NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE earnings_actuals (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
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
    UNIQUE(id, company_id)
);
CREATE INDEX earnings_actuals_asof_idx ON earnings_actuals(company_id, filed_date, period_start, period_end);
CREATE TABLE earnings_actual_edges (
    child_id UUID NOT NULL,
    parent_id UUID NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id),
    position INTEGER NOT NULL,
    PRIMARY KEY(child_id, position),
    CHECK(child_id <> parent_id),
    FOREIGN KEY(child_id, company_id) REFERENCES earnings_actuals(id, company_id),
    FOREIGN KEY(parent_id, company_id) REFERENCES earnings_actuals(id, company_id)
);
CREATE TABLE guidance_versions (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    content_hash TEXT NOT NULL UNIQUE,
    issued_start DATE NOT NULL,
    issued_end DATE NOT NULL CHECK(issued_end >= issued_start),
    issued_precision TEXT NOT NULL CHECK(issued_precision IN ('day','month','range')),
    filed_date DATE NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL CHECK(period_end >= period_start),
    metric TEXT NOT NULL,
    low NUMERIC,
    high NUMERIC,
    currency TEXT NOT NULL,
    basis TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('initial','reaffirmed','raised','lowered','withdrawn','reinstated')),
    accession TEXT NOT NULL,
    exhibit TEXT NOT NULL,
    source_url TEXT NOT NULL,
    quote TEXT NOT NULL CHECK(length(trim(quote)) > 0),
    original_verified BOOLEAN NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK((status = 'withdrawn' AND low IS NULL AND high IS NULL) OR
          (status <> 'withdrawn' AND low IS NOT NULL AND high IS NOT NULL AND low <= high)),
    CHECK(NOT original_verified OR status = 'initial'),
    CHECK(issued_precision <> 'day' OR issued_start = issued_end),
    UNIQUE(id, company_id)
);
CREATE INDEX guidance_versions_asof_idx ON guidance_versions(company_id, filed_date, issued_end);
CREATE TABLE hurdle_calculations (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    as_of DATE NOT NULL,
    formula_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    policy JSONB NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('ok','review','blocked')),
    reason_codes TEXT[] NOT NULL,
    remaining_low NUMERIC,
    remaining_high NUMERIC,
    growth_low NUMERIC,
    growth_high NUMERIC,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(id, company_id)
);
CREATE TABLE hurdle_input_edges (
    calculation_id UUID NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id),
    role TEXT NOT NULL CHECK(role IN ('guidance','actual_ytd','prior_annual','prior_ytd','prior_remaining')),
    actual_id UUID,
    guidance_id UUID,
    PRIMARY KEY(calculation_id, role),
    CHECK((role = 'guidance' AND guidance_id IS NOT NULL AND actual_id IS NULL) OR
          (role <> 'guidance' AND actual_id IS NOT NULL AND guidance_id IS NULL)),
    FOREIGN KEY(calculation_id, company_id) REFERENCES hurdle_calculations(id, company_id),
    FOREIGN KEY(actual_id, company_id) REFERENCES earnings_actuals(id, company_id),
    FOREIGN KEY(guidance_id, company_id) REFERENCES guidance_versions(id, company_id)
);
CREATE TABLE guidance_outcomes (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    as_of DATE NOT NULL,
    actual_id UUID NOT NULL,
    original_guidance_id UUID,
    latest_guidance_id UUID,
    result_issued_start DATE NOT NULL,
    result_issued_end DATE NOT NULL,
    result_issued_precision TEXT NOT NULL,
    filed_date DATE NOT NULL,
    result_accession TEXT NOT NULL,
    source_url TEXT NOT NULL,
    original_class TEXT CHECK(original_class IN ('below','within','above','not_comparable')),
    latest_class TEXT CHECK(latest_class IN ('below','within','above','not_comparable')),
    original_subsequently_withdrawn BOOLEAN NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY(actual_id, company_id) REFERENCES earnings_actuals(id, company_id),
    FOREIGN KEY(original_guidance_id, company_id) REFERENCES guidance_versions(id, company_id),
    FOREIGN KEY(latest_guidance_id, company_id) REFERENCES guidance_versions(id, company_id)
);
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['companies','earnings_actuals','earnings_actual_edges','guidance_versions',
        'hurdle_calculations','hurdle_input_edges','guidance_outcomes'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('GRANT SELECT ON %I TO anon, authenticated', t);
        EXECUTE format('GRANT ALL ON %I TO service_role', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO anon, authenticated USING (true)', t || '_select', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO service_role USING (true) WITH CHECK (true)', t || '_service_all', t);
    END LOOP;
END $$;
