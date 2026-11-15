-- Python-computed derived metrics, one row per deal (canonical or
-- not -- is_canonical is carried here too so a consumer can filter
-- without a join). Source of truth for anything the website shows
-- per-deal that isn't a raw extracted fact; see src/deal_metrics.py.
CREATE TABLE deal_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL UNIQUE REFERENCES deals(id) ON DELETE CASCADE,
    is_canonical BOOLEAN NOT NULL,
    acquirer_display TEXT NOT NULL,
    n_parties_contacted INT NOT NULL,
    n_bidders INT NOT NULL,
    n_proposals INT NOT NULL,
    first_price NUMERIC(14, 4),
    final_price NUMERIC(14, 4),
    pct_bump NUMERIC(12, 4),
    pct_bump_exclusion_reason TEXT,
    pct_bump_bucket TEXT,
    days_first_contact_to_signing INT,
    days_first_proposal_to_signing INT,
    first_bidder_won BOOLEAN,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX deal_metrics_is_canonical_idx ON deal_metrics (is_canonical);

-- One row per headline stat (src.bulk_stats.compute_all's top-level
-- keys). For a scalar stat (not a distribution, e.g. the single
-- first-bidder-won percentage), the value is stored in `median` and
-- p25/p75/min/max are left NULL -- a consumer should treat a stat as
-- scalar when p25/p75/min/max are all NULL.
CREATE TABLE headline_stats (
    name TEXT PRIMARY KEY,
    n INT NOT NULL,
    p25 NUMERIC,
    median NUMERIC,
    p75 NUMERIC,
    min NUMERIC,
    max NUMERIC,
    exclusions JSONB NOT NULL DEFAULT '{}',
    generated_at TIMESTAMPTZ NOT NULL,
    code_commit TEXT NOT NULL
);
