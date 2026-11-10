-- content_hash is sha256 of the record's own fields (sorted-key JSON),
-- excluding validation metadata -- it's how the loader stays idempotent:
-- re-loading the same immutable run folder always hashes identically and
-- hits the UNIQUE constraint, so review_status set by a human is never
-- clobbered by a reload. event_type is plain TEXT, not an enum, because
-- schemas.EventType is a Literal that's grown repeatedly as new deals
-- surface new event shapes -- an enum here would need a migration every
-- time that list grows, duplicating a distinction schemas.py already owns.
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES extraction_runs(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    date_text TEXT NOT NULL,
    date_start DATE,
    date_end DATE,
    date_precision date_precision NOT NULL,
    event_type TEXT NOT NULL,
    parties TEXT[] NOT NULL DEFAULT '{}',
    summary TEXT NOT NULL,
    source_paragraph_ids TEXT[] NOT NULL DEFAULT '{}',
    source_quotes TEXT[] NOT NULL DEFAULT '{}',
    passed BOOLEAN NOT NULL,
    failure_reasons TEXT[] NOT NULL DEFAULT '{}',
    review_status review_status NOT NULL DEFAULT 'unreviewed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, content_hash)
);

CREATE INDEX events_run_id_idx ON events (run_id);
