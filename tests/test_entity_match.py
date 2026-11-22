from src.entity_match import (
    governance_body_subject,
    is_acronym_of,
    is_same_entity,
)


def test_governance_body_subject_extracts_named_prefix():
    assert governance_body_subject("SST VI Special Committee") == "SST VI"
    assert governance_body_subject("AHL special committee") == "AHL"
    assert governance_body_subject("Terra BDC Special Committee") == "Terra BDC"
    assert governance_body_subject("SSGT III Board") == "SSGT III"


def test_governance_body_subject_bare_term_has_no_subject():
    assert governance_body_subject("Conflicts Committee") is None
    assert governance_body_subject("the Special Committee") is None


def test_governance_body_subject_non_governance_name_returns_none():
    assert governance_body_subject("Bending Spoons US") is None
    assert governance_body_subject("") is None
    assert governance_body_subject(None) is None


def test_is_acronym_of_regression_plain_initials_unaffected():
    assert is_acronym_of("USS", "United States Steel Corp") is True
    assert is_acronym_of("XYZ", "United States Steel Corp") is False


def test_is_acronym_of_numbered_series_keeps_trailing_token_whole():
    # Real stored pair for bulk_1852575_000119312526371874 (Strategic
    # Storage Trust VI / SST VI Special Committee) -- "VI" is kept as a
    # unit rather than reduced to "V".
    assert is_acronym_of("SST VI", "Strategic Storage Trust VI, Inc.") is True
    assert is_acronym_of("SSTVI", "Strategic Storage Trust VI, Inc.") is True


def test_is_acronym_of_numbered_series_does_not_overmatch():
    # A trailing word longer than 4 chars, or an unrelated short form,
    # must not spuriously match via the kept-suffix path.
    assert is_acronym_of("SST VI", "Strategic Storage Trust Seventeen, Inc.") is False
    assert is_acronym_of("ABC VI", "Strategic Storage Trust VI, Inc.") is False


def test_is_same_entity_unaffected_by_acronym_extension():
    # is_same_entity (the function src.dedup_deals clustering relies on)
    # never does initials/acronym matching at all -- confirms the
    # numbered-series extension to is_acronym_of has no path into dedup.
    assert is_same_entity("SST VI", "Strategic Storage Trust VI, Inc.") is False
    assert is_same_entity("SST VI Special Committee", "Strategic Storage Trust VI, Inc.") is False
