from src import classify_deal_type as cdt


def _proposal(proposer, quotes):
    return {"proposer": proposer, "source_quotes": quotes}


# --- _is_proposal_direction_reversed -----------------------------------


def test_proposal_direction_reversed_true_for_filer_proposing_to_acquire_acquirer_field():
    # Real shape: bulk_315293_000119312524045397 (Aon/NFP).
    proposals = [
        _proposal(
            "Aon plc",
            ["Aon delivered a non-binding indication of interest to NFP containing a proposal to acquire 100% of the equity of NFP."],
        )
    ]
    assert cdt._is_proposal_direction_reversed("Aon plc", "NFP", proposals) is True


def test_proposal_direction_reversed_false_when_normal_direction_evidence_exists():
    # Acquirer proposing to acquire target -- the ordinary, correctly
    # -labeled shape -- must never be flagged even if some other
    # unrelated quote in the same deal happens to mention "acquisition".
    proposals = [
        _proposal("Thoma Bravo", ["Thoma Bravo submitted a proposal to acquire all of the outstanding shares of Verint."]),
        _proposal("Verint", ["Verint's board discussed the proposed acquisition of its outstanding shares."]),
    ]
    assert cdt._is_proposal_direction_reversed("Verint", "Thoma Bravo", proposals) is False


def test_proposal_direction_reversed_false_with_no_acquire_language():
    proposals = [_proposal("Corebridge", ["Corebridge stockholders would own 52% of the combined company."])]
    assert cdt._is_proposal_direction_reversed("Equitable Holdings, Inc.", "Corebridge", proposals) is False


def test_proposal_direction_reversed_airtight_against_contrary_evidence():
    # One quote each way -- must NOT flag, since _is_filer_reversed's
    # own design note says this shape (the target also using "acquire"
    # language about itself) is common in an ordinary negotiation.
    proposals = [
        _proposal("Target Co", ["Target Co delivered a proposal to acquire Acquirer Co."]),
        _proposal("Acquirer Co", ["Acquirer Co submitted a proposal to acquire Target Co."]),
    ]
    assert cdt._is_proposal_direction_reversed("Target Co", "Acquirer Co", proposals) is False


# --- _is_new_holdco_merger ----------------------------------------------


def test_new_holdco_merger_true_for_double_dummy_structure(monkeypatch):
    # Verbatim real sentence from bulk_1411494_000119312521320881's own
    # cached filing text (Apollo/Athene) -- filings use the short
    # defined-term names ("Athene", "Apollo") in this kind of
    # structural recital, not the full legal name every time.
    text = (
        "as a result of the Transaction, each of Athene and Apollo "
        "will become a wholly owned subsidiary of Tango Holdings. The terms and conditions..."
    )
    monkeypatch.setattr(cdt, "_full_text", lambda slug: text)
    assert cdt._is_new_holdco_merger("bulk_fake", "Apollo Global Management, Inc.", "AHL special committee") is True


def test_new_holdco_merger_false_when_newco_matches_existing_party(monkeypatch):
    # "X will become a subsidiary of Y" where Y IS already the stored
    # target/acquirer is an ordinary single-acquirer sale, not a
    # double-dummy -- must not fire.
    text = "each of Party A and Party B will become a wholly owned subsidiary of Acquirer Co."
    monkeypatch.setattr(cdt, "_full_text", lambda slug: text)
    assert cdt._is_new_holdco_merger("bulk_fake", "Target Co", "Acquirer Co") is False


def test_new_holdco_merger_false_with_no_matching_text(monkeypatch):
    monkeypatch.setattr(cdt, "_full_text", lambda slug: "ordinary merger prose with no holdco language at all.")
    assert cdt._is_new_holdco_merger("bulk_fake", "Target Co", "Acquirer Co") is False


# --- _acquirer_is_target_governance_body --------------------------------


def test_acquirer_is_target_governance_body_true_for_literal_acronym():
    # Real shape: bulk_1852575_000119312526371874 (Strategic Storage
    # Trust VI / SST VI Special Committee).
    assert cdt._acquirer_is_target_governance_body("Strategic Storage Trust VI, Inc.", "SST VI Special Committee") is True


def test_acquirer_is_target_governance_body_true_for_bare_term():
    assert cdt._acquirer_is_target_governance_body("Landmark Infrastructure Partners LP", "Conflicts Committee") is True


def test_acquirer_is_target_governance_body_false_for_unrelated_company_committee():
    # Real shape: bulk_707388_000119312525162759 (STAR EQUITY HOLDINGS /
    # Hudson Special Committee) -- "Hudson" shares no name relationship
    # with the target at all, so this is someone ELSE's committee, not
    # a self-reference to the target.
    assert cdt._acquirer_is_target_governance_body("STAR EQUITY HOLDINGS, INC.", "Hudson Special Committee") is False


def test_acquirer_is_target_governance_body_false_for_ordinary_acquirer_name():
    assert cdt._acquirer_is_target_governance_body("Verint Systems Inc.", "Thoma Bravo") is False


# --- end-to-end wiring (no cached HTML needed -- a non-"bulk_" slug
# short-circuits every _full_text-dependent check to "", same as a
# curated deal) --------------------------------------------------------


def test_classify_deal_flags_proposal_direction_reversal_end_to_end():
    events = []
    proposals = [
        _proposal(
            "Aon plc",
            ["Aon delivered a non-binding indication of interest to NFP containing a proposal to acquire 100% of the equity of NFP."],
        )
    ]
    deal_type, excluded, reason = cdt.classify_deal("fake_slug", "Aon plc", "NFP", events, proposals)
    assert deal_type == "filer_is_acquirer"
    assert excluded is True
    assert reason is not None


def test_classify_deal_flags_governance_body_self_reference_end_to_end():
    deal_type, excluded, reason = cdt.classify_deal(
        "fake_slug", "Strategic Storage Trust VI, Inc.", "SST VI Special Committee", [], []
    )
    assert deal_type == "acquirer_is_target_governance_body"
    assert excluded is True


def test_classify_deal_leaves_ordinary_deal_included():
    deal_type, excluded, reason = cdt.classify_deal("fake_slug", "Verint Systems Inc.", "Thoma Bravo", [], [])
    assert deal_type == "acquisition"
    assert excluded is False
    assert reason is None
