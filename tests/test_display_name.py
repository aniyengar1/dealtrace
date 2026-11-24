from src.display_name import clean_display_name


def test_strips_legal_suffix_and_edgar_state_tag():
    assert clean_display_name("LIFECORE BIOMEDICAL, INC. \\DE\\") == "Lifecore Biomedical"


def test_strips_state_tag_slash_form():
    assert clean_display_name("WEINGARTEN REALTY INVESTORS /TX/") == "Weingarten Realty Investors"


def test_leaves_already_mixed_case_name_untouched():
    assert clean_display_name("Global Blood Therapeutics, Inc.") == "Global Blood Therapeutics"


def test_does_not_mistake_an_ordinary_word_for_an_acronym():
    # "END" is not in the whitelist, so it gets ordinary title-casing,
    # not preserved as if it were an initialism.
    assert clean_display_name("LANDS' END, INC.") == "Lands' End"


def test_preserves_initialism_with_internal_periods():
    # Regression: an unconditional trailing rstrip(",.") used to eat
    # the real trailing period off "H.I.G." even though it never
    # matched a legal suffix at all.
    assert clean_display_name("H.I.G.") == "H.I.G."


def test_preserves_curated_acronym_whitelist_entries():
    assert clean_display_name("USA TRUCK INC") == "USA Truck"
    assert clean_display_name("USA Rare Earth, Inc.") == "USA Rare Earth"
    assert clean_display_name("USAR") == "USAR"
    assert clean_display_name("SMTC CORP") == "SMTC"


def test_restores_stylized_capitalization_word_overrides():
    assert clean_display_name("VMWARE, INC.") == "VMware"
    assert clean_display_name("MARINEMAX INC") == "MarineMax"


def test_prefers_full_name_over_acronym_for_dfh():
    assert clean_display_name("DFH") == "Dream Finders Homes"


def test_handles_suffix_with_internal_periods():
    assert clean_display_name("BP p.l.c.") == "BP"


def test_leaves_short_non_whitelisted_token_unchanged():
    # Too short to confidently title-case either way.
    assert clean_display_name("XOMA (US) LLC") == "XOMA (US)"


def test_round4_spotcheck_acronym_casing_fixes():
    # Round-4 spot check: ordinary title-casing mangled real tickers
    # ("Cvs Health", "Hni", "Aes", "Itgr") -- all four are whitelisted,
    # not guessed.
    assert clean_display_name("CVS HEALTH CORP") == "CVS Health"
    assert clean_display_name("HNI CORP") == "HNI"
    assert clean_display_name("AES CORP") == "AES"
    assert clean_display_name("ITGR") == "ITGR"


def test_restores_avalonbay_stylized_capitalization():
    assert clean_display_name("AVALONBAY COMMUNITIES INC") == "AvalonBay Communities"


def test_lhc_group_keeps_group_not_just_the_bare_acronym():
    # "Group" is a generic legal suffix almost everywhere else, but
    # here it's part of the real, publicly traded name -- the override
    # restores it rather than leaving the suffix-stripped bare "LHC".
    assert clean_display_name("LHC GROUP, INC.") == "LHC Group"
