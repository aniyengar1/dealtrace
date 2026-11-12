-- Automated deal discovery results, from scanning EDGAR's quarterly
-- form.idx files for DEFM14A/PREM14A/SC 14D9/SC TO-T/S-4 filings and
-- grouping them into candidate deals (see src/discover.py). This is a
-- quick-check table, not an extraction target -- row presence here
-- doesn't imply the deal has (or will) go through the pipeline.
--
-- primary_accession is the globally-unique accession number of whichever
-- filing in the cluster was chosen as the deal's main record (preference
-- order: DEFM14A > SC 14D9 > S-4 > PREM14A > SC TO-T, non-amendment
-- preferred over "/A" within the same tier) -- the natural key for
-- idempotent re-runs. linked_filings holds every other filing (earlier
-- preliminary versions, amendments) grouped into the same ~12-month,
-- same-CIK cluster, which are part of the deal's paper trail but never
-- promoted to primary.
CREATE TABLE deal_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_cik TEXT NOT NULL,
    target_name TEXT NOT NULL,
    primary_form_type TEXT NOT NULL,
    primary_accession TEXT NOT NULL UNIQUE,
    primary_filed_date DATE NOT NULL,
    primary_file_name TEXT NOT NULL,
    linked_filings JSONB NOT NULL DEFAULT '[]',
    background_section_found BOOLEAN,
    background_word_count INT,
    consideration_type TEXT,
    consideration_value NUMERIC(14, 4),
    section_finder_error TEXT,
    fetch_error TEXT,
    checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX deal_candidates_cik_idx ON deal_candidates (target_cik);
CREATE INDEX deal_candidates_filed_date_idx ON deal_candidates (primary_filed_date);
