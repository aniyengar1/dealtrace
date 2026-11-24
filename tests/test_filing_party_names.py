from src.filing_party_names import extract_acquirer_from_filing, is_shell_name


def _html(text: str) -> str:
    return f"<html><body><p>{text}</p></body></html>"


def test_extracts_parent_with_descriptive_clause():
    html = _html(
        "by and among the Company, LFG Acquisition Holdings LLC, a subsidiary of the Company "
        "(“Opco” and, together with the Company, the “Company Entities”), "
        "BP Products North America Inc., a Maryland corporation (“Parent”), "
        "Condor RTM Inc., a Delaware corporation and a wholly owned subsidiary of Parent (“Merger Sub”)"
    )
    assert extract_acquirer_from_filing(html, "Archaea Energy Inc.") == "BP Products North America Inc"


def test_extracts_parent_with_long_descriptive_clause():
    html = _html(
        "Approval of the acquisition of OTI by Nayax Ltd., a company incorporated under the laws of "
        "the State of Israel whose shares are traded on the Tel Aviv Stock Exchange (“Parent”)"
    )
    assert extract_acquirer_from_filing(html, "ON TRACK INNOVATIONS LTD") == "Nayax Ltd"


def test_prefers_parent_over_shell_purchaser_in_tender_offer():
    html = _html(
        "the tender offer by Project Merci Merger Sub, Inc. (“Purchaser”), a Nevada corporation "
        "and wholly-owned indirect subsidiary of Biosynex SA, a French société anonyme (“Parent”)"
    )
    assert extract_acquirer_from_filing(html, "CHEMBIO DIAGNOSTICS, INC.") == "Biosynex SA"


def test_follows_subsidiary_of_relation_past_a_shell_name():
    html = _html(
        "the cash tender offer by HBP Merger Sub, Inc., a Delaware corporation (“Merger Sub”) "
        "and a wholly-owned subsidiary of Woodgrain Inc. (“Parent”)"
    )
    assert extract_acquirer_from_filing(html, "HUTTIG BUILDING PRODUCTS INC") == "Woodgrain Inc"


def test_does_not_use_a_distant_unrelated_subsidiary_of_clause():
    # The "subsidiary of the Company" clause describes an EARLIER,
    # different party (LFG) -- not BP's own definition -- so it must
    # not be used to cut BP's name away.
    html = _html(
        "by and among the Company, LFG Acquisition Holdings LLC, a subsidiary of the Company, "
        "BP Products North America Inc., a Maryland corporation (“Parent”)"
    )
    result = extract_acquirer_from_filing(html, "Archaea Energy Inc.")
    assert result == "BP Products North America Inc"


def test_prefers_affiliate_of_refinement_over_shell_name():
    html = _html(
        "with Rand Parent, LLC, a Delaware limited liability company (“Parent”), for $3.40 per share "
        "in cash. Parent is an affiliate of ATN International, Inc. and Freedom 3 Investments IV, LP"
    )
    assert extract_acquirer_from_filing(html, "ALASKA COMMUNICATIONS SYSTEMS GROUP INC") == "ATN International, Inc"


def test_prefers_does_business_as_refinement():
    html = _html(
        "the proposed acquisition of Avantax by Aretec Group, Inc., a Delaware corporation that does "
        "business as Cetera Holdings (“ Parent ”), for $26.00 per share"
    )
    assert extract_acquirer_from_filing(html, "AVANTAX, INC.") == "Cetera Holdings"


def test_falls_back_to_shell_name_when_no_refinement_found():
    html = _html("by and among Heidrick, Heron BidCo, LLC (“ Parent ”) and Heron Merger Sub, Inc.")
    result = extract_acquirer_from_filing(html, "HEIDRICK & STRUGGLES INTERNATIONAL INC")
    assert result == "Heron BidCo, LLC"
    assert is_shell_name(result)


def test_rejects_name_starting_with_address_fragment_in_favor_of_earlier_clean_match():
    html = _html(
        "the merger of the Company with and into 1776 Portfolio REIT Merger Sub, LLC "
        "(“REIT Merger Sub”), a Delaware limited liability company and wholly owned subsidiary of "
        "1776 Portfolio Investment, LLC (“Parent”), with REIT Merger Sub. "
        "c/o KSL Capital Partners, LLC 100 St. Paul Street, Suite 800 Denver, Colorado 80206 "
        "(720) 284-6400 1776 Portfolio Investment, LLC (“Parent”) is a Delaware limited liability company"
    )
    result = extract_acquirer_from_filing(html, "HERSHA HOSPITALITY TRUST")
    assert result == "1776 Portfolio Investment, LLC"


def test_does_not_split_and_company_as_a_connector():
    # "Eli Lilly and Company" is a real legal name -- "and" here is
    # part of the name, not a connector joining two different parties.
    html = _html(
        "the tender offer by Ridgeway Acquisition Corporation, a Delaware corporation (“Purchaser”) "
        "and an indirect wholly-owned subsidiary of Eli Lilly and Company, an Indiana corporation (“Parent”)"
    )
    assert extract_acquirer_from_filing(html, "Verve Therapeutics, Inc.") == "Eli Lilly and Company"


def test_returns_none_when_only_candidate_is_the_target_itself():
    html = _html("by and among Acme Inc. (“Company”), Acme Inc. (“Parent”)")
    assert extract_acquirer_from_filing(html, "Acme Inc.") is None


def test_returns_none_with_no_party_definitions():
    html = _html("This is a filing with no defined parties at all.")
    assert extract_acquirer_from_filing(html, "Acme Inc.") is None


def test_is_shell_name_detects_conventional_patterns():
    for name in ["Heron BidCo, LLC", "Rand Parent, LLC", "Oak-Eagle AcquireCo", "Pluto Acquisitionco", "Huron MergeCo"]:
        assert is_shell_name(name), name


def test_is_shell_name_detects_intermediate_vehicles():
    # Round-4 spot check: Avalara's acquirer_display showed "Lava
    # Intermediate" (the filing's own vehicle name) instead of the
    # already-correct, already-stored "Vista" -- "Intermediate" wasn't
    # a recognized shell marker at all, so the vehicle name won
    # unconditionally over a real, better heuristic answer.
    assert is_shell_name("Lava Intermediate, LLC")
    assert is_shell_name("Lava Intermediate")


def test_is_shell_name_detects_opaque_short_acronym():
    assert is_shell_name("LEWHP, LLC")
    assert not is_shell_name("BP Products North America Inc.")
    assert not is_shell_name("Biosynex SA")
