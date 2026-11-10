-- Freeform note a reviewer can attach when correcting or rejecting a
-- fact (the review UI's Reject action takes a required note; Correct's
-- is optional context for why a field was changed).
ALTER TABLE events ADD COLUMN reviewer_note TEXT;
ALTER TABLE proposals ADD COLUMN reviewer_note TEXT;
ALTER TABLE valuations ADD COLUMN reviewer_note TEXT;
