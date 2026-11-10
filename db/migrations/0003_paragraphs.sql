-- One row per paragraph produced by sections.parse_paragraphs. paragraph_id
-- (e.g. "p00459") is globally unique within a deal across every section --
-- IDs are assigned by one pass over the whole filing, then sections are
-- carved out as slices of that list -- so (deal_id, paragraph_id) is a
-- real natural key, not an approximation.
CREATE TABLE paragraphs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
    paragraph_id TEXT NOT NULL,
    section_key TEXT NOT NULL,
    level INT,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (deal_id, paragraph_id)
);

CREATE INDEX paragraphs_deal_id_idx ON paragraphs (deal_id);
