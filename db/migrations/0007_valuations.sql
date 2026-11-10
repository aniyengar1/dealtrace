CREATE TABLE valuations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES extraction_runs(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    advisor TEXT NOT NULL,
    method TEXT NOT NULL,
    metric TEXT NOT NULL,
    multiple_low NUMERIC(14, 4),
    multiple_high NUMERIC(14, 4),
    implied_price_low NUMERIC(14, 4),
    implied_price_high NUMERIC(14, 4),
    key_assumptions TEXT[] NOT NULL DEFAULT '{}',
    source_paragraph_ids TEXT[] NOT NULL DEFAULT '{}',
    source_quotes TEXT[] NOT NULL DEFAULT '{}',
    passed BOOLEAN NOT NULL,
    failure_reasons TEXT[] NOT NULL DEFAULT '{}',
    review_status review_status NOT NULL DEFAULT 'unreviewed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, content_hash)
);

CREATE INDEX valuations_run_id_idx ON valuations (run_id);
