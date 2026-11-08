from src.score import (
    gold_event_date_range,
    match_events,
    match_proposals,
    normalize_party,
    score_extraction,
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


def test_match_events_exact_day_match():
    gold = [{"date": "2023-04-10", "date_precision": "day", "event_type": "board_meeting"}]
    extracted = [{"date_start": "2023-04-10", "date_end": "2023-04-10", "event_type": "board_meeting"}]
    result = match_events(gold, extracted)
    assert len(result["matches"]) == 1
    assert not result["misses"]
    assert not result["extras"]


def test_match_events_month_precision_matches_any_day_in_month():
    gold = [{"date": "2022-01", "date_precision": "month", "event_type": "advisor_engagement"}]
    extracted = [
        {"date_start": "2022-01-17", "date_end": "2022-01-17", "event_type": "advisor_engagement"}
    ]
    result = match_events(gold, extracted)
    assert len(result["matches"]) == 1


def test_match_events_requires_same_event_type():
    gold = [{"date": "2023-04-10", "date_precision": "day", "event_type": "board_meeting"}]
    extracted = [{"date_start": "2023-04-10", "date_end": "2023-04-10", "event_type": "other"}]
    result = match_events(gold, extracted)
    assert not result["matches"]
    assert len(result["misses"]) == 1
    assert len(result["extras"]) == 1


def test_match_events_date_outside_window_is_a_miss():
    gold = [{"date": "2023-04-10", "date_precision": "day", "event_type": "board_meeting"}]
    extracted = [{"date_start": "2023-04-11", "date_end": "2023-04-11", "event_type": "board_meeting"}]
    result = match_events(gold, extracted)
    assert not result["matches"]
    assert len(result["misses"]) == 1
    assert len(result["extras"]) == 1


def test_match_events_is_one_to_one():
    # Two identical gold events must each claim a separate extracted event,
    # not both match the same one.
    gold = [
        {"date": "2023-04-10", "date_precision": "day", "event_type": "board_meeting"},
        {"date": "2023-04-10", "date_precision": "day", "event_type": "board_meeting"},
    ]
    extracted = [{"date_start": "2023-04-10", "date_end": "2023-04-10", "event_type": "board_meeting"}]
    result = match_events(gold, extracted)
    assert len(result["matches"]) == 1
    assert len(result["misses"]) == 1
    assert not result["extras"]


def test_match_proposals_matches_on_date_and_price():
    gold = [{"date": "2022-02-04", "proposer": "Cisco", "recipient": "Splunk", "price_low": 193, "price_high": 193}]
    extracted = [
        {"date": "February 4, 2022", "proposer": "Party B", "recipient": "Party A", "price_low": 193.0, "price_high": 193.0}
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


def test_normalize_party_maps_anonymized_labels():
    assert normalize_party("Party A") == "Splunk"
    assert normalize_party("Party B") == "Cisco"
    assert normalize_party("Qatalyst Partners") == "Qatalyst Partners"


def test_score_extraction_core_recall_counts_only_core_events():
    gold = {
        "events": [
            {"id": "E1", "date": "2023-04-10", "date_precision": "day", "event_type": "a", "core": True},
            {"id": "E2", "date": "2023-04-11", "date_precision": "day", "event_type": "b", "core": False},
        ],
        "proposals": [],
    }
    # Only the non-core event is extracted; core recall must be 0/1 even
    # though overall recall is 1/2.
    extraction = {
        "Event": [{"date_start": "2023-04-11", "date_end": "2023-04-11", "event_type": "b"}],
        "Proposal": [],
    }
    result = score_extraction(gold, extraction)
    assert result["events"]["n_matched"] == 1
    assert result["events"]["core_n_gold"] == 1
    assert result["events"]["core_n_matched"] == 0


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
                "proposer": "Party B",
                "recipient": "Party A",
                "price_low": 193.0,
                "price_high": 193.0,
                "proposal_kind": "formal_bid",  # wrong kind, but matched on date+price
            }
        ],
    }
    result = score_extraction(gold, extraction)
    assert result["proposals"]["n_matched"] == 1
    assert result["proposals"]["proposal_kind_correct"] == 0
    assert result["proposals"]["proposer_recipient_correct"] == 1
