from src import classify_deal_type as cdt


def _proposal(proposer, quotes):
    return {"proposer": proposer, "source_quotes": quotes}


# --- _is_proposal_direction_reversed -----------------------------------


def test_proposal_direction_reversed_true_for_filer_proposing_to_acquire_acquirer_field():
    # Real shape: bulk_315293_000119312524045397 (Aon/NFP). A non-"bulk_"
    # slug short-circuits _full_text to "" (no I/O), same as a curated deal.
    proposals = [
        _proposal(
            "Aon plc",
            ["Aon delivered a non-binding indication of interest to NFP containing a proposal to acquire 100% of the equity of NFP."],
        )
    ]
    assert cdt._is_proposal_direction_reversed("fake_slug", "Aon plc", "NFP", proposals) is True


def test_proposal_direction_reversed_false_when_normal_direction_evidence_exists():
    # Acquirer proposing to acquire target -- the ordinary, correctly
    # -labeled shape -- must never be flagged even if some other
    # unrelated quote in the same deal happens to mention "acquisition".
    proposals = [
        _proposal("Thoma Bravo", ["Thoma Bravo submitted a proposal to acquire all of the outstanding shares of Verint."]),
        _proposal("Verint", ["Verint's board discussed the proposed acquisition of its outstanding shares."]),
    ]
    assert cdt._is_proposal_direction_reversed("fake_slug", "Verint", "Thoma Bravo", proposals) is False


def test_proposal_direction_reversed_false_with_no_acquire_language():
    proposals = [_proposal("Corebridge", ["Corebridge stockholders would own 52% of the combined company."])]
    assert cdt._is_proposal_direction_reversed("fake_slug", "Equitable Holdings, Inc.", "Corebridge", proposals) is False


def test_proposal_direction_reversed_airtight_against_contrary_evidence():
    # One quote each way -- must NOT flag, since _is_filer_reversed's
    # own design note says this shape (the target also using "acquire"
    # language about itself) is common in an ordinary negotiation.
    proposals = [
        _proposal("Target Co", ["Target Co delivered a proposal to acquire Acquirer Co."]),
        _proposal("Acquirer Co", ["Acquirer Co submitted a proposal to acquire Target Co."]),
    ]
    assert cdt._is_proposal_direction_reversed("fake_slug", "Target Co", "Acquirer Co", proposals) is False


def test_proposal_direction_reversed_ignores_negated_acquisition_phrase():
    # Real shape: bulk_1371217_000110465921049773 (ReShape/Obalon) --
    # "contemplating a combination... rather than an acquisition of
    # Obalon" REJECTS the acquisition framing, it doesn't assert it.
    proposals = [
        _proposal(
            "ReShape",
            ["term sheet contemplating a combination of the companies rather than an acquisition of Obalon's assets."],
        )
    ]
    assert cdt._is_proposal_direction_reversed("fake_slug", "ReShape Lifesciences Inc.", "Obalon", proposals) is False


def test_proposal_direction_reversed_final_subsidiary_structure_overrides_early_proposal(monkeypatch):
    # Real shape: bulk_1754820_000114036123041374 (Desktop Metal/Stratasys)
    # -- Desktop Metal's own EARLY proposal was to acquire Stratasys, but
    # the deal's final, legally operative structure (its own merger
    # -agreement recital) has Desktop Metal becoming Stratasys's
    # subsidiary -- the correctly-labeled, final direction, which must
    # win over the early, later-superseded offer.
    proposals = [
        _proposal(
            "Desktop Metal, Inc.",
            ["a non-binding, preliminary indication of interest of Desktop Metal to acquire Stratasys in a stock-for-stock transaction."],
        )
    ]
    monkeypatch.setattr(
        cdt, "_full_text", lambda slug: "Desktop Metal surviving the Merger as a wholly owned subsidiary of Stratasys."
    )
    assert cdt._is_proposal_direction_reversed("bulk_fake", "Desktop Metal, Inc.", "Stratasys", proposals) is False


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


# --- vote-based S-4 rules (_is_s4_vote_based_reversed/_is_s4_merger_of_equals/_is_s4_buyer_side_only_vote) --------


def test_s4_vote_based_reversed_true_when_acquirer_field_party_adopts(monkeypatch):
    # Real shape: bulk_1018724_000110465926089294 (Amazon/Globalstar) --
    # the ACQUIRER field's own party ("Globalstar") is the one shown
    # adopting the merger agreement; the target field's party ("AMAZON
    # COM INC") is never shown doing so.
    monkeypatch.setattr(
        cdt, "_full_text", lambda slug: "Globalstar stockholders adopt the merger agreement and approve the merger."
    )
    assert cdt._is_s4_vote_based_reversed("fake_slug", "AMAZON COM INC", "Globalstar", "S-4") is True


def test_s4_vote_based_reversed_false_when_target_already_adopts(monkeypatch):
    monkeypatch.setattr(
        cdt, "_full_text", lambda slug: "Target Co stockholders adopt the merger agreement and approve the merger."
    )
    assert cdt._is_s4_vote_based_reversed("fake_slug", "Target Co", "Acquirer Co", "S-4") is False


def test_non_s4_form_type_is_not_flagged_by_any_vote_based_check():
    assert cdt._is_s4_vote_based_reversed("fake_slug", "Target Co", "Acquirer Co", "DEFM14A") is False
    assert cdt._is_s4_vote_based_reversed("fake_slug", "Target Co", "Acquirer Co", None) is False
    assert cdt._is_s4_merger_of_equals("fake_slug", "Target Co", "Acquirer Co", "DEFM14A") is False
    assert cdt._is_s4_buyer_side_only_vote("fake_slug", "Target Co", "Acquirer Co", "DEFM14A") is False


def test_s4_vote_based_reversed_respects_no_vote_required_negation(monkeypatch):
    # Real shape: PotlatchDeltic/CatchMark -- "the absence of any
    # required vote of the PotlatchDeltic stockholders to approve the
    # Company Merger" is PotlatchDeltic's own closing-condition
    # representation that IT needs no vote, not evidence it has one.
    # Without this guard, the real acquirer's negated non-vote would
    # wrongly satisfy this check.
    monkeypatch.setattr(
        cdt,
        "_full_text",
        lambda slug: (
            "CatchMark stockholders approve the Company Merger. The representations include the absence "
            "of any required vote of the PotlatchDeltic stockholders to approve the Company Merger."
        ),
    )
    assert cdt._is_s4_vote_based_reversed("fake_slug", "PotlatchDeltic", "CatchMark", "S-4") is True


def test_s4_merger_of_equals_true_for_explicit_phrase(monkeypatch):
    # Real shape: Hut 8/USBTC.
    monkeypatch.setattr(cdt, "_full_text", lambda slug: "This transaction is structured as a merger of equals.")
    assert cdt._is_s4_merger_of_equals("fake_slug", "Hut 8 Corp.", "USBTC", "S-4") is True


def test_s4_merger_of_equals_ignores_comparable_transactions_screening_boilerplate(monkeypatch):
    # Real shape: Raymond James/TriState Capital -- a fairness-opinion
    # precedent-transactions screen ("excluding any Merger of Equals
    # (as defined by S&P Global Market Intelligence)") describes the
    # advisor's own screening methodology, not this deal's structure.
    monkeypatch.setattr(
        cdt,
        "_full_text",
        lambda slug: "deal value between $500 million and $2.5 billion, excluding any Merger of Equals (as defined by S&P).",
    )
    assert cdt._is_s4_merger_of_equals("fake_slug", "TriState Capital", "Raymond James", "S-4") is False


def test_s4_merger_of_equals_does_not_fire_on_dual_statutory_vote_alone(monkeypatch):
    # Real shape: LINKBANCORP/GNB, Mesa Air Group/Republic -- both
    # sides' shareholders formally adopting their own merger agreement
    # is an ordinary STATUTORY requirement for plenty of bank-holding
    # -company and REIT mergers where one side is clearly the
    # acquirer, not evidence of a genuine merger of equals.
    monkeypatch.setattr(
        cdt,
        "_full_text",
        lambda slug: (
            "GNB shareholders will be asked to adopt the merger agreement. "
            "LINK shareholders will be asked to adopt the merger agreement."
        ),
    )
    assert cdt._is_s4_merger_of_equals("fake_slug", "GNB", "LINKBANCORP, Inc.", "S-4") is False


def test_s4_buyer_side_only_vote_true_when_only_acquirer_field_party_votes_on_issuance(monkeypatch):
    # Real shape: Bally's/Gamesys -- only Bally's (stored target field)
    # votes, and only on its own share issuance; Gamesys has no
    # described vote at all.
    monkeypatch.setattr(
        cdt,
        "_full_text",
        lambda slug: "Bally's stockholders will be asked to approve the issuance of shares (the Share Issuance Proposal).",
    )
    assert cdt._is_s4_buyer_side_only_vote("fake_slug", "Bally's Corp", "Gamesys", "S-4") is True


def test_s4_buyer_side_only_vote_false_when_either_party_adopts(monkeypatch):
    monkeypatch.setattr(
        cdt, "_full_text", lambda slug: "Target Co stockholders adopt the merger agreement and approve the merger."
    )
    assert cdt._is_s4_buyer_side_only_vote("fake_slug", "Target Co", "Acquirer Co", "S-4") is False


def test_classify_deal_flags_s4_vote_based_reversal_end_to_end(monkeypatch):
    monkeypatch.setattr(
        cdt, "_full_text", lambda slug: "Globalstar stockholders adopt the merger agreement and approve the merger."
    )
    deal_type, excluded, reason = cdt.classify_deal(
        "fake_slug", "AMAZON COM INC", "Globalstar", [], [], form_type="S-4"
    )
    assert deal_type == "filer_is_acquirer"
    assert excluded is True


def test_classify_deal_includes_s4_merger_of_equals_with_distinct_type(monkeypatch):
    monkeypatch.setattr(cdt, "_full_text", lambda slug: "This transaction is structured as a merger of equals.")
    deal_type, excluded, reason = cdt.classify_deal("fake_slug", "Hut 8 Corp.", "USBTC", [], [], form_type="S-4")
    assert deal_type == "merger_of_equals"
    assert excluded is False


def test_classify_deal_excludes_s4_buyer_side_only_vote(monkeypatch):
    monkeypatch.setattr(
        cdt,
        "_full_text",
        lambda slug: "Bally's stockholders will be asked to approve the issuance of shares (the Share Issuance Proposal).",
    )
    deal_type, excluded, reason = cdt.classify_deal("fake_slug", "Bally's Corp", "Gamesys", [], [], form_type="S-4")
    assert deal_type == "buyer_side_s4_vote"
    assert excluded is True


# --- _S4_VOTE_MANUAL_OVERRIDES -------------------------------------------


def test_manual_override_include_wins_over_absent_vote_evidence(monkeypatch):
    # Marel hf./John Bean Technologies: the manual "include" override
    # must win even though _full_text (monkeypatched empty here) has
    # no "adopt the merger agreement" evidence at all -- Marel's real
    # approval is a tender offer, a shape the text-only rule can't see.
    monkeypatch.setattr(cdt, "_full_text", lambda slug: "")
    slug = "bulk_1433660_000119312524139600"
    assert cdt._S4_VOTE_MANUAL_OVERRIDES[slug] == "include"
    deal_type, excluded, reason = cdt.classify_deal(slug, "Marel hf.", "John Bean Technologies Corporation", [], [], form_type="S-4")
    assert excluded is False


def test_manual_override_exclude_wins_over_fabricated_vote_evidence(monkeypatch):
    # Twin Vee: even if the text happened to contain adopt-vote
    # language (it does, for the holdco's own reorganization vote),
    # the manual "exclude" override (complex_structure: a holdco
    # reorganization with no real second party) must still win.
    monkeypatch.setattr(
        cdt, "_full_text", lambda slug: "Twin Vee Inc. stockholders vote to adopt the merger agreement."
    )
    slug = "bulk_1855509_000173112222001537"
    assert cdt._S4_VOTE_MANUAL_OVERRIDES[slug] == "complex_structure"
    deal_type, excluded, reason = cdt.classify_deal(
        slug, "Twin Vee PowerCats, Co.", "Unknown", [], [], form_type="S-4"
    )
    assert deal_type == "complex_structure"
    assert excluded is True
