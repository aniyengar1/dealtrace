from src.bulk_quality_check import _resolve_target_placeholder, guess_acquirer


def test_resolve_target_placeholder_maps_generic_terms():
    assert _resolve_target_placeholder("Company", "Acme Inc") == "Acme Inc"
    assert _resolve_target_placeholder("the Company", "Acme Inc") == "Acme Inc"
    assert _resolve_target_placeholder("Board", "Acme Inc") == "Acme Inc"
    assert _resolve_target_placeholder("Special Committee", "Acme Inc") == "Acme Inc"


def test_resolve_target_placeholder_leaves_real_names_and_acquirer_terms_untouched():
    assert _resolve_target_placeholder("Parent", "Acme Inc") == "Parent"
    assert _resolve_target_placeholder("Merger Sub", "Acme Inc") == "Merger Sub"
    assert _resolve_target_placeholder("Real Acquirer Co", "Acme Inc") == "Real Acquirer Co"


def test_resolve_target_placeholder_passes_through_none():
    assert _resolve_target_placeholder(None, "Acme Inc") is None


def test_guess_acquirer_picks_the_most_common_non_target_name():
    proposals = [
        {"proposer": "Real Acquirer Co", "recipient": "Acme Inc"},
        {"proposer": "Real Acquirer Co", "recipient": "Acme Inc"},
        {"proposer": "Acme Inc", "recipient": "Real Acquirer Co"},
    ]
    assert guess_acquirer("Acme Inc", proposals) == "Real Acquirer Co"


def test_guess_acquirer_resolves_target_placeholders_before_counting():
    # Without resolving "Company" to the target first, this generic
    # placeholder would itself be the most common "non-target" name.
    proposals = [
        {"proposer": "Company", "recipient": "Real Acquirer Co"},
        {"proposer": "Company", "recipient": "Real Acquirer Co"},
        {"proposer": "Real Acquirer Co", "recipient": "Company"},
    ]
    assert guess_acquirer("Acme Inc", proposals) == "Real Acquirer Co"


def test_guess_acquirer_returns_none_with_no_proposals():
    assert guess_acquirer("Acme Inc", []) is None


def test_guess_acquirer_never_returns_an_anonymized_placeholder():
    # "Company A" outnumbers "Real Acquirer Co" by raw mention count --
    # parties often stay anonymous through most of the negotiation --
    # but a placeholder must never win just because it's more frequent.
    proposals = [
        {"proposer": "Company A", "recipient": "Acme Inc"},
        {"proposer": "Company A", "recipient": "Acme Inc"},
        {"proposer": "Real Acquirer Co", "recipient": "Acme Inc"},
    ]
    assert guess_acquirer("Acme Inc", proposals) == "Real Acquirer Co"


def test_guess_acquirer_uses_signing_event_only_when_proposals_have_no_real_name():
    # Every proposal is still anonymized -- frequency-counting finds no
    # real candidate at all, so the signing event's named party is the
    # only source of a real answer.
    proposals = [
        {"proposer": "Company A", "recipient": "Acme Inc"},
        {"proposer": "Company A", "recipient": "Acme Inc"},
    ]
    events = [{"event_type": "signing", "parties": ["Acme Inc", "Real Acquirer Co"]}]
    assert guess_acquirer("Acme Inc", proposals, events) == "Real Acquirer Co"


def test_guess_acquirer_never_lets_signing_event_override_a_good_frequency_answer():
    # A real name already wins on frequency; the signing event's own
    # language can itself be generic ("Purchaser") even when an earlier
    # proposal already named the real acquirer (seen live: "WHP Global"
    # for Lands' End, whose signing event used "Purchaser" instead) --
    # the signing event must never be consulted, let alone override,
    # when frequency already has a good answer.
    proposals = [
        {"proposer": "Real Acquirer Co", "recipient": "Acme Inc"},
        {"proposer": "Real Acquirer Co", "recipient": "Acme Inc"},
    ]
    events = [{"event_type": "signing", "parties": ["Acme Inc", "Purchaser"]}]
    assert guess_acquirer("Acme Inc", proposals, events) == "Real Acquirer Co"


def test_guess_acquirer_prefers_latest_signing_event_in_the_fallback():
    # An earlier, unrelated signing in the target's own history (e.g. a
    # prior SPAC-formation agreement) must not be mistaken for the real
    # merger's signing when there's no real proposal name to fall back
    # on either.
    proposals = []
    events = [
        {"event_type": "signing", "date_start": "2020-01-01", "parties": ["Acme Inc", "Old Unrelated Co"]},
        {"event_type": "signing", "date_start": "2023-06-01", "parties": ["Acme Inc", "Real Acquirer Co"]},
    ]
    assert guess_acquirer("Acme Inc", proposals, events) == "Real Acquirer Co"


def test_guess_acquirer_falls_back_when_signing_event_has_no_usable_name():
    proposals = []
    events = [{"event_type": "signing", "parties": ["Acme Inc", "Company A"]}]
    assert guess_acquirer("Acme Inc", proposals, events) is None


def test_guess_acquirer_returns_none_when_only_placeholders_available():
    proposals = [{"proposer": "Company A", "recipient": "Acme Inc"}]
    assert guess_acquirer("Acme Inc", proposals) is None
