from src.deal_metrics import KNOWN_SHORT_NAME_EXPANSIONS, _is_safe_fuller_name, resolve_acquirer_display


def test_is_safe_fuller_name_accepts_legal_suffix_completions():
    assert _is_safe_fuller_name("Diamondback Energy, Inc.", "Diamondback")
    assert _is_safe_fuller_name("Brookfield Asset Management Inc.", "Brookfield")
    assert _is_safe_fuller_name("XOMA (US) LLC", "XOMA")
    assert _is_safe_fuller_name("Biogen MA Inc.", "Biogen")
    assert _is_safe_fuller_name("Maiden Holdings North America, Ltd.", "Maiden")


def test_is_safe_fuller_name_rejects_organizational_references():
    # These are REFERENCES to the acquirer, not fuller forms of its name.
    assert not _is_safe_fuller_name("SeaSpine Board", "SeaSpine")
    assert not _is_safe_fuller_name("AkzoNobel Boards", "AkzoNobel")
    assert not _is_safe_fuller_name("Rorschach Merger Sub", "Rorschach")
    assert not _is_safe_fuller_name("Zymeworks Merger Sub 1", "Zymeworks")
    assert not _is_safe_fuller_name("New Mountain fund", "New Mountain")
    assert not _is_safe_fuller_name("NFP Seller", "NFP")
    assert not _is_safe_fuller_name("Peak Bio Supporting Holders", "Peak Bio")


def test_is_safe_fuller_name_rejects_anonymized_placeholder_suffix():
    assert not _is_safe_fuller_name("Transocean Party A", "Transocean")
    assert not _is_safe_fuller_name("Valaris Party B", "Valaris")


def test_is_safe_fuller_name_rejects_combining_two_entities():
    assert not _is_safe_fuller_name("GIP and EQT consortium", "GIP")
    assert not _is_safe_fuller_name("Thoma Bravo and UserZoom", "Thoma Bravo")


def test_is_safe_fuller_name_rejects_bare_ticker_concatenation():
    # "FSKR" is a DIFFERENT fund's ticker that happens to start with
    # "FSK", not "FSK" with more words appended.
    assert not _is_safe_fuller_name("FSKR", "FSK")


def test_is_safe_fuller_name_rejects_numbered_sibling_fund():
    # "GBDC 3" is a different, numbered sibling fund -- not "GBDC" with
    # extra words, even though it's a longer string starting the same way.
    assert not _is_safe_fuller_name("GBDC 3", "GBDC")


def test_is_safe_fuller_name_accepts_real_structural_suffix():
    assert _is_safe_fuller_name("MSD Partners", "MSD")
    assert _is_safe_fuller_name("Barings BDC", "Barings")
    assert _is_safe_fuller_name("CSR OP", "CSR")


def test_resolve_acquirer_display_uses_curated_expansion():
    assert resolve_acquirer_display("NSC", "UNITED STATES STEEL CORP", [], []) == "Nippon Steel Corporation"


def test_resolve_acquirer_display_prefers_fuller_local_mention():
    proposals = [{"proposer": "Diamondback Energy, Inc.", "recipient": "Endeavor"}, {"proposer": "Diamondback", "recipient": "Endeavor"}]
    assert resolve_acquirer_display("Diamondback", "Endeavor", proposals, []) == "Diamondback Energy, Inc."


def test_resolve_acquirer_display_falls_back_to_stored_value():
    assert resolve_acquirer_display("Pfizer", "Global Blood Therapeutics, Inc.", [], []) == "Pfizer"


def test_known_short_name_expansions_is_small_and_curated():
    # Deliberately small -- a wrong guess here is worse than the short
    # form, so this is documentation as much as it is a test.
    assert KNOWN_SHORT_NAME_EXPANSIONS["NSC"] == "Nippon Steel Corporation"
