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
