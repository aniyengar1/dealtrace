-- Clean, website-ready display names and a basic price sanity flag,
-- on top of the raw/best-available values deal_metrics already had.
-- See src/display_name.py for how these are derived.
ALTER TABLE deal_metrics
    ADD COLUMN target_display TEXT,
    ADD COLUMN price_plausible BOOLEAN;
