from src.deal_metrics import KNOWN_SHORT_NAME_EXPANSIONS, _curated_display_names, _is_safe_fuller_name, resolve_acquirer_display


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
    # Also suffix-stripped/cleaned, same as target_display.
    assert resolve_acquirer_display("NSC", "UNITED STATES STEEL CORP", [], []) == "Nippon Steel"


def test_resolve_acquirer_display_prefers_fuller_local_mention():
    proposals = [{"proposer": "Diamondback Energy, Inc.", "recipient": "Endeavor"}, {"proposer": "Diamondback", "recipient": "Endeavor"}]
    assert resolve_acquirer_display("Diamondback", "Endeavor", proposals, []) == "Diamondback Energy"


def test_resolve_acquirer_display_replaces_placeholder_with_undisclosed():
    assert resolve_acquirer_display("Parent", "Acme Inc", [], []) == "Undisclosed"
    assert resolve_acquirer_display("Company A", "Acme Inc", [], []) == "Undisclosed"
    assert resolve_acquirer_display("Purchaser", "Acme Inc", [], []) == "Undisclosed"


def test_resolve_acquirer_display_replaces_committee_with_undisclosed():
    assert resolve_acquirer_display("Special Committee", "Acme Inc", [], []) == "Undisclosed"
    assert resolve_acquirer_display("Conflicts Committee", "Acme Inc", [], []) == "Undisclosed"


def test_resolve_acquirer_display_replaces_self_reference_with_undisclosed():
    assert resolve_acquirer_display("USS", "UNITED STATES STEEL CORP", [], []) == "Undisclosed"
    assert resolve_acquirer_display("Acme Inc", "Acme Inc", [], []) == "Undisclosed"


def test_resolve_acquirer_display_falls_back_to_stored_value():
    assert resolve_acquirer_display("Pfizer", "Global Blood Therapeutics, Inc.", [], []) == "Pfizer"


def test_resolve_acquirer_display_resolves_named_committee_to_its_subject():
    # Real shape: bulk_707388_000119312525162759 (STAR EQUITY HOLDINGS /
    # Hudson Special Committee) -- "Hudson" is a different real company
    # (not the target), just never named beyond its own committee here.
    # Bare "Hudson" is strictly better than "Undisclosed", even with no
    # fuller mention anywhere in the deal's own extracted text.
    assert resolve_acquirer_display("Hudson Special Committee", "STAR EQUITY HOLDINGS, INC.", [], []) == "Hudson"


def test_resolve_acquirer_display_prefers_fuller_mention_of_committee_subject():
    proposals = [{"proposer": "Hudson Bay Partners, LLC", "recipient": "STAR EQUITY HOLDINGS, INC."}]
    assert (
        resolve_acquirer_display("Hudson Special Committee", "STAR EQUITY HOLDINGS, INC.", proposals, [])
        == "Hudson Bay Partners"
    )


def test_resolve_acquirer_display_self_referential_committee_stays_undisclosed():
    # Real shape: bulk_1852575_000119312526371874 (Strategic Storage
    # Trust VI / SST VI Special Committee) -- the subject IS the target
    # itself, so there's no real second party to resolve to at all.
    assert (
        resolve_acquirer_display("SST VI Special Committee", "Strategic Storage Trust VI, Inc.", [], [])
        == "Undisclosed"
    )


def test_resolve_acquirer_display_never_picks_up_a_law_firm_reference():
    # Real shape: bulk_1674356_000119312522181607 (Terra Property Trust
    # / Terra BDC Special Committee) -- "Terra BDC Company Counsel" is
    # the company's own lawyers, not a fuller legal name for "Terra BDC".
    proposals = [{"proposer": "Terra BDC Company Counsel", "recipient": "Terra Property Trust, Inc."}]
    assert (
        resolve_acquirer_display("Terra BDC Special Committee", "Terra Property Trust, Inc.", proposals, [])
        == "Terra Bdc"
    )


def test_known_short_name_expansions_is_small_and_curated():
    # Deliberately small -- a wrong guess here is worse than the short
    # form, so this is documentation as much as it is a test.
    assert KNOWN_SHORT_NAME_EXPANSIONS["NSC"] == "Nippon Steel Corporation"


def test_curated_display_names_parses_the_richer_acquirer_from_deal_name():
    # Zendesk's own acquirer field is just "Consortium" -- the full
    # story lives in deal_name, and must never fall through to
    # resolve_acquirer_display's heuristic (which would reject
    # "Consortium" as generic and show "Undisclosed").
    target, acquirer = _curated_display_names("zendesk")
    assert target == "Zendesk"
    assert acquirer == "Hellman & Friedman and Permira"


def test_resolve_acquirer_display_prefers_named_sponsor_over_generic_consortium():
    # Real shape: bulk_1135185_000110465922109861 (Atlas Air Worldwide /
    # "Consortium") -- the filing's own "Parent" definition resolves to
    # a named shell ("Rand Parent"), which previously won unconditionally
    # once "Consortium" was flagged generic. The real sponsors are named
    # in an earlier joint proposal AND corroborated by the signing event
    # itself, so they must win over the shell.
    proposals = [
        {"proposer": "Hill City, JFLCO and Apollo", "recipient": "Atlas Air Worldwide Holdings Inc", "date_resolved": "2021-06-01"},
        {"proposer": "Consortium", "recipient": "Atlas Air Worldwide Holdings Inc", "date_resolved": "2022-07-30"},
    ]
    events = [{"parties": ["Atlas Air Worldwide Holdings Inc", "Hill City", "JFLCO", "Apollo"]}]
    assert (
        resolve_acquirer_display("Consortium", "Atlas Air Worldwide Holdings Inc", proposals, events)
        == "Hill City, JFLCO and Apollo"
    )


def test_resolve_acquirer_display_requires_event_corroboration_for_named_sponsor():
    # An early, later-superseded proposal naming a real company is not
    # by itself evidence that the company is who the deal closed with
    # (Option Care Health: an early "CD&R and McKesson"-style proposal
    # from months before signing, with the actual signing/announcement
    # never mentioning them, would be a wrong guess). With no
    # corroborating event, stay with the plain generic-term handling
    # (Undisclosed) rather than surface an unconfirmed name.
    proposals = [
        {"proposer": "Real Sponsor Co", "recipient": "Acme Inc", "date_resolved": "2024-01-01"},
        {"proposer": "Consortium", "recipient": "Acme Inc", "date_resolved": "2024-06-01"},
    ]
    assert resolve_acquirer_display("Consortium", "Acme Inc", proposals, []) == "Undisclosed"


def test_resolve_acquirer_display_prefers_filing_vehicle_only_when_no_named_sponsor_exists():
    # No real sponsor named anywhere, so the named (if uninformative)
    # shell from the filing stays the fallback -- still better than
    # Undisclosed, unchanged from the existing behavior.
    assert resolve_acquirer_display("Consortium", "Acme Inc", [], []) == "Undisclosed"


def test_curated_display_names_covers_every_curated_deal():
    from src.run import DEALS

    for slug in DEALS:
        target, acquirer = _curated_display_names(slug)
        assert target and acquirer
        assert acquirer not in {"Consortium", "Unknown", "Undisclosed"}
