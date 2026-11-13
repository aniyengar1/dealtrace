-- subject_cik/subject_sic come from the filing's own SGML header (the
-- <SUBJECT-COMPANY>/<FILER> block), fetched separately from the quick
-- check -- the only way to find a tender offer's TRUE target when
-- form.idx's own CIK column names the bidder instead (see
-- src/classify.py: SC TO-T is filed under the bidder's CIK often enough
-- that grouping by form.idx's CIK alone mis-clusters it as its own
-- "deal" when the real target already has its own SC 14D9 row).
--
-- classification is a best-effort, no-LLM read of SIC code + text
-- signals in the cached document -- not authoritative, just enough to
-- separate real operating-company M&A from SPAC mechanics and from
-- everything else (debt/warrant exchanges, bank holding mergers,
-- reorganizations, going-private squeeze-outs).
ALTER TABLE deal_candidates
    ADD COLUMN subject_cik TEXT,
    ADD COLUMN subject_sic TEXT,
    ADD COLUMN classification TEXT
        CHECK (classification IN ('public_company_acquisition', 'spac_de_spac', 'other')),
    ADD COLUMN classification_reason TEXT,
    ADD COLUMN linked_sc14d9_accession TEXT;
