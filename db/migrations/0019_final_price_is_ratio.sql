-- True when deal_metrics.final_price should be displayed as a stock
-- -exchange ratio ("0.36x"), not a dollar amount -- the final
-- proposal's own consideration_type is 'stock' AND its own source
-- quotes never spell out the stored number as a dollar figure (an
-- "implied value of $X per share" is a real, common convention even
-- for an all-stock deal, so plenty of consideration_type='stock' rows
-- still store a genuine dollar price). See
-- src.bulk_stats.compute_final_price_is_ratio_for_deal.
ALTER TABLE deal_metrics
    ADD COLUMN final_price_is_ratio BOOLEAN;
