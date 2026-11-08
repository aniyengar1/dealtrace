from src.score import (
    extracted_proposal_date,
    gold_event_date_range,
    match_events,
    match_proposals,
    normalize_name,
    score_extraction,
    summary_overlap,
)


def test_gold_event_date_range_day_precision():
    gold = {"date": "2023-04-10", "date_precision": "day"}
    start, end = gold_event_date_range(gold)
    assert str(start) == "2023-04-10"
    assert str(end) == "2023-04-10"


def test_gold_event_date_range_month_precision_spans_whole_month():
    gold = {"date": "2022-01", "date_precision": "month"}
    start, end = gold_event_date_range(gold)
    assert str(start) == "2022-01-01"
    assert str(end) == "2022-01-31"


def test_gold_event_date_range_range_precision_spans_given_bounds():
    gold = {"date": "2023-05-03/2023-06-19", "date_precision": "range"}
    start, end = gold_event_date_range(gold)
    assert str(start) == "2023-05-03"
    assert str(end) == "2023-06-19"


def test_summary_overlap_handles_verb_noun_form_differences():
    # "engagement" vs "engaged" must still register as overlap -- a crude
    # stem (prefix), not an exact token match, is what makes this pass.
    a = "Formal engagement letter with Qatalyst Partners"
    b = "Splunk formally engaged a financial advisor"
    assert summary_overlap(a, b) > 0


def test_match_events_matches_on_same_paragraph_even_with_weak_summary():
    gold = [
        {
            "date": "2023-04-10",
            "date_precision": "day",
            "paragraph_id": "p1",
            "summary": "completely unrelated wording on purpose",
        }
    ]
    extracted = [
        {
            "date_start": "2023-04-10",
            "date_end": "2023-04-10",
            "source_paragraph_ids": ["p1"],
            "summary": "nothing in common here either",
        }
    ]
    result = match_events(gold, extracted)
    assert len(result["matches"]) == 1


def test_match_events_matches_on_strong_summary_overlap_without_same_paragraph():
    gold = [
        {
            "date": "2023-04-10",
            "date_precision": "day",
            "paragraph_id": "p1",
            "summary": "Board of Directors approved the formation of a Transaction Committee",
        }
    ]
    extracted = [
        {
            "date_start": "2023-04-10",
            "date_end": "2023-04-10",
            "source_paragraph_ids": ["p999"],  # different paragraph
            "summary": "The Board approved forming a Transaction Committee",
        }
    ]
    result = match_events(gold, extracted)
    assert len(result["matches"]) == 1


def test_match_events_does_not_match_on_event_type_alone():
    # Same event_type, same date, but neither same paragraph nor overlapping
    # summary -- must be a miss. event_type is not a matching criterion.
    gold = [
        {
            "date": "2023-04-10",
            "date_precision": "day",
            "paragraph_id": "p1",
            "event_type": "board_meeting",
            "summary": "Board discusses the proposed transaction price",
        }
    ]
    extracted = [
        {
            "date_start": "2023-04-10",
            "date_end": "2023-04-10",
            "source_paragraph_ids": ["p999"],
            "event_type": "board_meeting",
            "summary": "Completely unrelated matter entirely",
        }
    ]
    result = match_events(gold, extracted)
    assert not result["matches"]
    assert len(result["misses"]) == 1
    assert len(result["extras"]) == 1


def test_match_events_matches_despite_different_event_type():
    # A content match (same paragraph) must win even when event_type
    # differs -- event_type accuracy is scored separately, not gated here.
    gold = [
        {
            "date": "2023-04-10",
            "date_precision": "day",
            "paragraph_id": "p1",
            "event_type": "board_authorization",
            "summary": "irrelevant for this test",
        }
    ]
    extracted = [
        {
            "date_start": "2023-04-10",
            "date_end": "2023-04-10",
            "source_paragraph_ids": ["p1"],
            "event_type": "board_meeting",
            "summary": "also irrelevant",
        }
    ]
    result = match_events(gold, extracted)
    assert len(result["matches"]) == 1


def test_match_events_date_outside_window_is_a_miss():
    gold = [{"date": "2023-04-10", "date_precision": "day", "paragraph_id": "p1", "summary": "x"}]
    extracted = [
        {"date_start": "2023-04-11", "date_end": "2023-04-11", "source_paragraph_ids": ["p1"], "summary": "x"}
    ]
    result = match_events(gold, extracted)
    assert not result["matches"]
    assert len(result["misses"]) == 1
    assert len(result["extras"]) == 1


def test_match_events_global_assignment_resolves_shared_paragraph_correctly():
    # Two gold events share one paragraph_id (a paragraph with two facts),
    # but only one extracted event cites it, and its content clearly
    # belongs to the second gold event. A naive per-gold-event greedy pass
    # (processed in list order) would hand it to the first gold event just
    # because "same paragraph" is satisfied; global assignment must instead
    # give it to whichever gold event it actually matches in content.
    gold = [
        {
            "id": "G1",
            "date": "2022-01",
            "date_precision": "month",
            "paragraph_id": "p1",
            "summary": "Splunk engages Qatalyst Partners as a financial advisor",
        },
        {
            "id": "G2",
            "date": "2022-01-23",
            "date_precision": "day",
            "paragraph_id": "p1",
            "summary": "Cisco and Splunk sign a confidentiality agreement",
        },
    ]
    extracted = [
        {
            "date_start": "2022-01-23",
            "date_end": "2022-01-23",
            "source_paragraph_ids": ["p1"],
            "summary": "Cisco and Splunk entered into a confidentiality agreement",
        }
    ]
    result = match_events(gold, extracted)
    assert len(result["matches"]) == 1
    matched_gold, _ = result["matches"][0]
    assert matched_gold["id"] == "G2"
    assert result["misses"] == [gold[0]]


def test_extracted_proposal_date_prefers_date_resolved_over_literal_text():
    rec = {"date": "later that evening", "date_resolved": "2023-08-30"}
    assert str(extracted_proposal_date(rec)) == "2023-08-30"


def test_extracted_proposal_date_falls_back_to_parsing_literal_text():
    rec = {"date": "August 30, 2023"}
    assert str(extracted_proposal_date(rec)) == "2023-08-30"


def test_match_proposals_matches_via_resolved_relative_date():
    gold = [{"date": "2023-08-30", "proposer": "Cisco", "recipient": "Splunk", "price_low": 156, "price_high": 156}]
    extracted = [
        {
            "date": "later that evening",
            "date_resolved": "2023-08-30",
            "proposer": "Cisco",
            "recipient": "Splunk",
            "price_low": 156.0,
            "price_high": 156.0,
        }
    ]
    result = match_proposals(gold, extracted)
    assert len(result["matches"]) == 1


def test_match_proposals_matches_on_date_and_price():
    gold = [{"date": "2022-02-04", "proposer": "Cisco", "recipient": "Splunk", "price_low": 193, "price_high": 193}]
    extracted = [
        {"date": "February 4, 2022", "proposer": "Cisco", "recipient": "Splunk", "price_low": 193.0, "price_high": 193.0}
    ]
    result = match_proposals(gold, extracted)
    assert len(result["matches"]) == 1


def test_match_proposals_price_mismatch_is_a_miss():
    gold = [{"date": "2022-02-04", "proposer": "Cisco", "recipient": "Splunk", "price_low": 193, "price_high": 193}]
    extracted = [{"date": "February 4, 2022", "price_low": 200.0, "price_high": 200.0}]
    result = match_proposals(gold, extracted)
    assert not result["matches"]
    assert len(result["misses"]) == 1
    assert len(result["extras"]) == 1


def test_normalize_name_is_case_and_whitespace_only_not_a_name_bridge():
    assert normalize_name("Cisco") == normalize_name("  cisco ")
    # Anonymized labels must NOT be treated as equivalent to the real name.
    assert normalize_name("Party B") != normalize_name("Cisco")


def test_score_extraction_core_recall_counts_only_core_events():
    gold = {
        "events": [
            {"id": "E1", "date": "2023-04-10", "date_precision": "day", "paragraph_id": "p1", "summary": "a", "core": True},
            {"id": "E2", "date": "2023-04-11", "date_precision": "day", "paragraph_id": "p2", "summary": "b", "core": False},
        ],
        "proposals": [],
    }
    # Only the non-core event is extracted; core recall must be 0/1 even
    # though overall recall is 1/2.
    extraction = {
        "Event": [{"date_start": "2023-04-11", "date_end": "2023-04-11", "source_paragraph_ids": ["p2"], "summary": "b"}],
        "Proposal": [],
    }
    result = score_extraction(gold, extraction)
    assert result["events"]["n_matched"] == 1
    assert result["events"]["core_n_gold"] == 1
    assert result["events"]["core_n_matched"] == 0


def test_score_extraction_event_type_accuracy_among_matched():
    gold = {
        "events": [
            {"id": "E1", "date": "2023-04-10", "date_precision": "day", "paragraph_id": "p1", "summary": "x", "event_type": "board_authorization"}
        ],
        "proposals": [],
    }
    extraction = {
        "Event": [
            {
                "date_start": "2023-04-10",
                "date_end": "2023-04-10",
                "source_paragraph_ids": ["p1"],
                "summary": "x",
                "event_type": "board_meeting",  # content matches (same paragraph), type doesn't
                "parties": [],
            }
        ],
        "Proposal": [],
    }
    result = score_extraction(gold, extraction)
    assert result["events"]["n_matched"] == 1
    assert result["events"]["event_type_correct"] == 0
    assert result["events"]["event_type_total"] == 1


def test_score_extraction_event_parties_accuracy_requires_gold_names_present():
    gold = {
        "events": [
            {
                "id": "E1",
                "date": "2023-04-10",
                "date_precision": "day",
                "paragraph_id": "p1",
                "summary": "x",
                "parties": ["Cisco", "Splunk"],
            }
        ],
        "proposals": [],
    }
    extraction = {
        "Event": [
            {
                "date_start": "2023-04-10",
                "date_end": "2023-04-10",
                "source_paragraph_ids": ["p1"],
                "summary": "x",
                "parties": ["Party A", "Party B"],  # anonymized, not a real-name match
            }
        ],
        "Proposal": [],
    }
    result = score_extraction(gold, extraction)
    assert result["events"]["n_matched"] == 1
    assert result["events"]["parties_correct"] == 0


def test_score_extraction_proposal_kind_and_party_accuracy():
    gold = {
        "events": [],
        "proposals": [
            {
                "id": "P1",
                "date": "2022-02-04",
                "proposer": "Cisco",
                "recipient": "Splunk",
                "price_low": 193,
                "price_high": 193,
                "proposal_kind": "non_binding_indication",
            }
        ],
    }
    extraction = {
        "Event": [],
        "Proposal": [
            {
                "date": "February 4, 2022",
                "proposer": "Party B",  # anonymized -- must NOT count as matching "Cisco"
                "recipient": "Party A",
                "price_low": 193.0,
                "price_high": 193.0,
                "proposal_kind": "formal_bid",  # wrong kind, but still matched on date+price
            }
        ],
    }
    result = score_extraction(gold, extraction)
    assert result["proposals"]["n_matched"] == 1
    assert result["proposals"]["proposal_kind_correct"] == 0
    assert result["proposals"]["proposer_recipient_correct"] == 0


def test_score_extraction_proposer_recipient_matches_real_names():
    gold = {
        "events": [],
        "proposals": [
            {
                "id": "P1",
                "date": "2022-02-04",
                "proposer": "Cisco",
                "recipient": "Splunk",
                "price_low": 193,
                "price_high": 193,
                "proposal_kind": "non_binding_indication",
            }
        ],
    }
    extraction = {
        "Event": [],
        "Proposal": [
            {
                "date": "February 4, 2022",
                "proposer": "  cisco ",
                "recipient": "SPLUNK",
                "price_low": 193.0,
                "price_high": 193.0,
                "proposal_kind": "non_binding_indication",
            }
        ],
    }
    result = score_extraction(gold, extraction)
    assert result["proposals"]["proposer_recipient_correct"] == 1
