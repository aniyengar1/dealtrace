-- Materialized public research reports; writes remain in the service pipeline.
CREATE TABLE earnings_metric_facts (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    metric_key TEXT NOT NULL,
    concept TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    filed_date DATE NOT NULL,
    accession TEXT NOT NULL,
    unit TEXT NOT NULL,
    value NUMERIC NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX earnings_metrics_lookup ON earnings_metric_facts(company_id, filed_date, period_end);
CREATE TABLE earnings_company_reports (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    as_of DATE NOT NULL,
    report_version TEXT NOT NULL,
    hurdle_id UUID NOT NULL REFERENCES hurdle_calculations(id),
    forecast_id UUID NOT NULL,
    forecast_method TEXT NOT NULL,
    forecast_estimate NUMERIC,
    benchmark_estimate NUMERIC,
    forecast_status TEXT NOT NULL CHECK(forecast_status IN ('experimental', 'blocked')),
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX earnings_reports_lookup ON earnings_company_reports(company_id, as_of DESC, created_at DESC);
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['earnings_metric_facts', 'earnings_company_reports'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('GRANT SELECT ON %I TO anon, authenticated', t);
        EXECUTE format('GRANT ALL ON %I TO service_role', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO anon, authenticated USING (true)', t || '_select', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO service_role USING (true) WITH CHECK (true)', t || '_service_all', t);
    END LOOP;
END $$;
