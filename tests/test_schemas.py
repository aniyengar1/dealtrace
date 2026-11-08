import pytest
from pydantic import ValidationError

from src.schemas import Event, Proposal

EVENT_BASE = {
    "date_text": "April 10, 2023",
    "date_start": "2023-04-10",
    "date_end": "2023-04-10",
    "date_precision": "day",
    "parties": ["Splunk"],
    "summary": "The Board of Directors met.",
    "source_paragraph_ids": ["p1"],
    "source_quotes": ["the Board of Directors convened a meeting"],
}

PROPOSAL_BASE = {
    "date": "February 4, 2022",
    "proposer": "Cisco",
    "recipient": "Splunk",
    "price_low": 193.0,
    "price_high": 193.0,
    "consideration_type": "cash",
    "proposal_kind": "non_binding_indication",
    "status": "open",
    "source_paragraph_ids": ["p1"],
    "source_quotes": ["$193 per share in cash"],
}


@pytest.mark.parametrize(
    "event_type",
    [
        "withdrawal",
        "re_engagement",
        "rejection",
        "advisor_engagement",
        "projections_shared",
        "market_check_decision",
        "board_authorization",
        "board_approval",
        "press_leak",
        "management_condition",
        "draft_agreement",
        "announcement",
        "discussion",
        "diligence_request",
    ],
)
def test_event_accepts_new_event_types(event_type):
    Event.model_validate({**EVENT_BASE, "event_type": event_type})


def test_event_rejects_unknown_event_type():
    with pytest.raises(ValidationError):
        Event.model_validate({**EVENT_BASE, "event_type": "not_a_real_type"})


def test_proposal_accepts_revised_bid_kind():
    Proposal.model_validate({**PROPOSAL_BASE, "proposal_kind": "revised_bid"})


@pytest.mark.parametrize("status", ["open", "rejected", "superseded", "accepted", "withdrawn"])
def test_proposal_accepts_each_status(status):
    Proposal.model_validate({**PROPOSAL_BASE, "status": status})


def test_proposal_rejects_unknown_status():
    with pytest.raises(ValidationError):
        Proposal.model_validate({**PROPOSAL_BASE, "status": "pending"})


def test_event_requires_at_least_one_source_quote():
    with pytest.raises(ValidationError):
        Event.model_validate({**EVENT_BASE, "event_type": "other", "source_quotes": []})


def test_event_rejects_more_than_three_source_quotes():
    with pytest.raises(ValidationError):
        Event.model_validate(
            {**EVENT_BASE, "event_type": "other", "source_quotes": ["a", "b", "c", "d"]}
        )


def test_event_accepts_up_to_three_source_quotes():
    Event.model_validate({**EVENT_BASE, "event_type": "other", "source_quotes": ["a", "b", "c"]})
