-- Marks duplicate rows for the same real-world transaction (e.g. a
-- curated deal and its bulk-discovered counterpart, or a DEFM14A and
-- the counterparty's S-4 for the same merger) without deleting
-- anything -- src.dedup_deals decides which row in a duplicate group
-- is canonical and points every other member at it. Every deal starts
-- canonical; a deal is excluded from headline stats exactly when
-- is_canonical is false.
ALTER TABLE deals
    ADD COLUMN is_canonical BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN duplicate_of UUID REFERENCES deals(id);

CREATE INDEX deals_duplicate_of_idx ON deals (duplicate_of);
