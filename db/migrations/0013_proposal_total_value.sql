-- Some proposals quote an aggregate/enterprise value (e.g. "ascribed a
-- value of at least $25 billion to Endeavor") rather than a per-share
-- price -- a correct extraction of the filing text, just the wrong
-- shape for price_low/price_high, which are NUMERIC(14,4) sized for
-- per-share dollar amounts and overflow on multi-billion-dollar
-- figures. total_value_low/high hold that same figure when it's too
-- large to be a per-share price (src.load_db.upsert_proposal decides
-- which column a given value belongs in); both NULL for the normal,
-- per-share case.
ALTER TABLE proposals
    ADD COLUMN total_value_low NUMERIC(20, 2),
    ADD COLUMN total_value_high NUMERIC(20, 2);
