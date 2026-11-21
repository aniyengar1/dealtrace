-- A genuine, included (not excluded_from_stats) sale process can still
-- have zero extracted Proposal records for reasons that have nothing
-- to do with the deal's own structure -- the Background of the Merger
-- section's bid history just didn't parse into Proposal records this
-- run (Twitter/Musk, New Relic, Skillsoft/Codecademy). data_quality_flag
-- marks these so the website can note the gap on the deal page while
-- src.bulk_stats keeps them out of every proposal-derived cross-deal
-- stat (bidders, proposal counts, price bump) without hiding the deal
-- or dropping it from parties_contacted/first-bidder stats, which don't
-- depend on a Proposal record existing. NULL means no known data-
-- quality issue; the only value in use today is
-- 'proposals_not_extracted', but the column is a free-text reason
-- (like pct_bump_exclusion_reason) rather than a boolean so a future,
-- differently-shaped gap doesn't need a new column.
ALTER TABLE deal_metrics
    ADD COLUMN data_quality_flag TEXT;
