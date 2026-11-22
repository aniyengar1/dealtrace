-- Deal size, read deterministically from the filing's own text (see
-- src/deal_size.py) rather than computed or estimated. Each number
-- carries its own source quote, the same convention as every other
-- extracted fact. Both are nullable: a curated deal has no cached
-- full-text HTML to parse at all, and most bulk filings never state
-- an aggregate transaction/equity value outright.
-- NUMERIC, not BIGINT -- node-postgres returns a BIGINT (oid 20) column
-- as a JS string by default to avoid silent precision loss, and
-- src/lib/db.ts only registers a type parser for NUMERIC (oid 1700,
-- parsed as a float) and DATE, the same convention final_price/pct_bump
-- already use. A share count safely fits in NUMERIC/a JS number either
-- way (nowhere near Number.MAX_SAFE_INTEGER).
ALTER TABLE deal_metrics
    ADD COLUMN shares_outstanding NUMERIC(20, 0),
    ADD COLUMN shares_outstanding_quote TEXT,
    ADD COLUMN aggregate_value NUMERIC(20, 2),
    ADD COLUMN aggregate_value_quote TEXT;
