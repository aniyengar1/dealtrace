-- status is the Proposal's own lifecycle (open/rejected/superseded/
-- accepted/withdrawn, schemas.ProposalStatus) -- distinct from
-- review_status, which is this schema's human-review state and applies
-- uniformly across events/proposals/valuations.
CREATE TABLE proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES extraction_runs(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    date_text TEXT NOT NULL,
    date_resolved DATE,
    proposer TEXT NOT NULL,
    recipient TEXT NOT NULL,
    price_low NUMERIC(14, 4),
    price_high NUMERIC(14, 4),
    premium_pct NUMERIC(8, 4),
    currency TEXT,
    consideration_type TEXT NOT NULL,
    proposal_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    source_paragraph_ids TEXT[] NOT NULL DEFAULT '{}',
    source_quotes TEXT[] NOT NULL DEFAULT '{}',
    passed BOOLEAN NOT NULL,
    failure_reasons TEXT[] NOT NULL DEFAULT '{}',
    review_status review_status NOT NULL DEFAULT 'unreviewed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, content_hash)
);

CREATE INDEX proposals_run_id_idx ON proposals (run_id);
