-- Classifies each deal's transaction structure and marks the ones that
-- shouldn't count toward cross-deal stats/listings at all (a spin-off
-- distribution, an affiliated-manager fund-complex merger, a filing
-- where the filer turned out to be the acquirer not the target) vs.
-- ones that are real sale processes but worth a visible label (a
-- reverse merger). See src.classify_deal_type.
ALTER TABLE deal_metrics
    ADD COLUMN deal_type TEXT,
    ADD COLUMN excluded_from_stats BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN exclusion_reason TEXT;

CREATE INDEX deal_metrics_excluded_from_stats_idx ON deal_metrics (excluded_from_stats);
