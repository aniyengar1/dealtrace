-- days_first_contact_to_signing is excluded from the public
-- headline_stats table and the website as of the round-3 spot-check
-- (5 of 9 field errors found were first-contact dates, the least
-- reliable extracted signal in the pipeline) -- see src.bulk_stats's
-- compute_all(). The column itself stays: still computed and stored
-- per deal for internal/future use, just never surfaced or
-- aggregated publicly until first-contact extraction improves.
COMMENT ON COLUMN deal_metrics.days_first_contact_to_signing IS
    'Experimental -- not used in public headline_stats or the website. Round-3 spot-check found this field the least reliable of those extracted (5 of 9 field errors were first-contact dates). Kept for internal/future use only.';
