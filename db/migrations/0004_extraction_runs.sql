-- One row per data/output/runs/<timestamp>_<deal>_<model>_<prompt_version>/
-- folder the pipeline wrote. run_dir is that folder name verbatim and is
-- the natural key -- the pipeline never overwrites a run folder, so it's
-- stable and unique by construction.
CREATE TABLE extraction_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    run_dir TEXT NOT NULL UNIQUE,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX extraction_runs_deal_id_idx ON extraction_runs (deal_id);
