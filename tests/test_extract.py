import pytest
from google.genai import errors

from src import extract
from src.extract import (
    ExtractionError,
    _call_gemini,
    _is_daily_quota_exhausted,
    apply_relative_date_fallback,
    chunk_paragraphs_by_count,
    paragraph_anchor_dates,
)
from src.schemas import BackgroundExtraction, Event, Proposal


def _quota_error(quota_ids: list[str]) -> errors.ClientError:
    return errors.ClientError(
        429,
        {
            "error": {
                "code": 429,
                "status": "RESOURCE_EXHAUSTED",
                "message": "You exceeded your current quota. Please retry in 12h.",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [{"quotaId": qid} for qid in quota_ids],
                    }
                ],
            }
        },
    )


def _server_error(code: int) -> errors.ServerError:
    return errors.ServerError(code, {"error": {"code": code, "status": "UNAVAILABLE", "message": "overloaded"}})


class FakeUsageMetadata:
    prompt_token_count = 10
    candidates_token_count = 5
    total_token_count = 15


class FakeResponse:
    model_version = "fake-model-version"
    usage_metadata = FakeUsageMetadata()
    text = "{}"


class FakeModels:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


@pytest.fixture(autouse=True)
def isolate_quota_and_cache(tmp_path, monkeypatch):
    # _call_gemini records real quota/cache state on success; redirect both
    # to a scratch dir so these tests never touch the repo's real files.
    monkeypatch.setattr(extract, "QUOTA_FILE", tmp_path / "quota_usage.json")
    monkeypatch.setattr(extract, "CACHE_DIR", tmp_path)


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(extract.time, "sleep", lambda _seconds: None)


def test_is_daily_quota_exhausted_true_for_per_day_violation():
    exc = _quota_error(["GenerateRequestsPerDayPerProjectPerModel-FreeTier"])
    assert _is_daily_quota_exhausted(exc)


def test_is_daily_quota_exhausted_false_for_per_minute_only():
    exc = _quota_error(["GenerateRequestsPerMinutePerProjectPerModel-FreeTier"])
    assert not _is_daily_quota_exhausted(exc)


def test_is_daily_quota_exhausted_true_when_mixed_with_per_minute():
    # The API can report per-minute AND per-day violations on one response;
    # the per-day one alone must still make this unretryable.
    exc = _quota_error(
        [
            "GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
            "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
        ]
    )
    assert _is_daily_quota_exhausted(exc)


def test_daily_quota_exhaustion_fails_immediately_without_retry(monkeypatch):
    client = FakeClient([_quota_error(["GenerateRequestsPerDayPerProjectPerModel-FreeTier"])])
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    with pytest.raises(ExtractionError, match="daily quota exhausted"):
        _call_gemini("prompt", BackgroundExtraction, "fake-model")

    assert client.models.calls == 1


def test_per_minute_429_is_retried_then_succeeds(monkeypatch):
    client = FakeClient(
        [_quota_error(["GenerateRequestsPerMinutePerProjectPerModel-FreeTier"]), FakeResponse()]
    )
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    item, usage = _call_gemini("prompt", BackgroundExtraction, "fake-model")

    assert item == {}
    assert usage.calls == 1
    assert client.models.calls == 2


def test_server_overload_is_retried_then_succeeds(monkeypatch):
    client = FakeClient([_server_error(503), _server_error(503), FakeResponse()])
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    item, usage = _call_gemini("prompt", BackgroundExtraction, "fake-model")

    assert item == {}
    assert client.models.calls == 3


def test_transient_errors_exhaust_retry_budget(monkeypatch):
    client = FakeClient([_server_error(503)] * extract.MAX_TRANSIENT_RETRIES)
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    with pytest.raises(ExtractionError, match="transient-error retries"):
        _call_gemini("prompt", BackgroundExtraction, "fake-model")

    assert client.models.calls == extract.MAX_TRANSIENT_RETRIES


def test_non_retryable_client_error_raises_immediately(monkeypatch):
    client = FakeClient([errors.ClientError(400, {"error": {"code": 400, "message": "bad request"}})])
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    with pytest.raises(errors.ClientError):
        _call_gemini("prompt", BackgroundExtraction, "fake-model")

    assert client.models.calls == 1


def _paras(n):
    return [{"id": f"p{i:05d}", "text": f"paragraph {i}"} for i in range(n)]


def test_chunk_by_count_splits_into_target_number_of_chunks():
    chunks = chunk_paragraphs_by_count(_paras(67), 3)
    assert len(chunks) == 3
    # every paragraph appears exactly once, in order, split on boundaries
    assert [p for chunk in chunks for p in chunk] == _paras(67)


def test_chunk_by_count_roughly_balances_chunk_sizes():
    chunks = chunk_paragraphs_by_count(_paras(67), 3)
    sizes = [len(c) for c in chunks]
    assert max(sizes) - min(sizes) <= 2


def test_chunk_by_count_of_one_returns_single_chunk():
    paras = _paras(10)
    assert chunk_paragraphs_by_count(paras, 1) == [paras]


def test_chunk_by_count_never_exceeds_paragraph_count():
    chunks = chunk_paragraphs_by_count(_paras(2), 5)
    assert len(chunks) == 2
    assert all(len(c) == 1 for c in chunks)


def _event(**overrides):
    base = dict(
        date_text="later that day",
        date_start=None,
        date_end=None,
        date_precision="unknown",
        event_type="other",
        parties=["Cisco", "Splunk"],
        summary="x",
        source_paragraph_ids=["p1"],
        source_quotes=["x"],
    )
    base.update(overrides)
    return Event.model_validate(base)


def _proposal(**overrides):
    base = dict(
        date="later that day",
        date_resolved=None,
        proposer="Cisco",
        recipient="Splunk",
        consideration_type="cash",
        proposal_kind="revised_bid",
        status="open",
        source_paragraph_ids=["p1"],
        source_quotes=["x"],
    )
    base.update(overrides)
    return Proposal.model_validate(base)


def test_paragraph_anchor_dates_carries_forward_the_last_absolute_date():
    paras = [
        {"id": "p1", "text": "On August 30, 2023, the parties spoke."},
        {"id": "p2", "text": "Later that day, Robbins called Steele."},
        {"id": "p3", "text": "On August 31, 2023, a new offer was made."},
    ]
    anchors = paragraph_anchor_dates(paras)
    assert str(anchors["p1"]) == "2023-08-30"
    assert str(anchors["p2"]) == "2023-08-30"  # inherits from p1, no date of its own
    assert str(anchors["p3"]) == "2023-08-31"  # updated by its own date


def test_paragraph_anchor_dates_is_none_before_any_absolute_date_seen():
    paras = [{"id": "p1", "text": "Earlier that week, they had spoken."}]
    anchors = paragraph_anchor_dates(paras)
    assert anchors["p1"] is None


def test_apply_relative_date_fallback_fills_missing_event_date():
    paras = [
        {"id": "p1", "text": "On August 30, 2023, the parties spoke."},
        {"id": "p2", "text": "Later that day, Robbins called Steele."},
    ]
    event = _event(source_paragraph_ids=["p2"])
    merged = {"events": [event], "proposals": []}
    apply_relative_date_fallback(merged, paras)
    assert str(event.date_start) == "2023-08-30"
    assert str(event.date_end) == "2023-08-30"
    assert event.date_precision == "day"
    assert event.date_text == "later that day"  # original phrase untouched


def test_apply_relative_date_fallback_fills_missing_proposal_date():
    paras = [
        {"id": "p1", "text": "On August 30, 2023, the parties spoke."},
        {"id": "p2", "text": "Later that day, Robbins called Steele with a new price."},
    ]
    proposal = _proposal(source_paragraph_ids=["p2"])
    merged = {"events": [], "proposals": [proposal]}
    apply_relative_date_fallback(merged, paras)
    assert str(proposal.date_resolved) == "2023-08-30"
    assert proposal.date == "later that day"


def test_apply_relative_date_fallback_never_overrides_a_resolved_date():
    paras = [{"id": "p1", "text": "On August 30, 2023, the parties spoke."}]
    event = _event(source_paragraph_ids=["p1"], date_start="2023-01-01", date_precision="day")
    merged = {"events": [event], "proposals": []}
    apply_relative_date_fallback(merged, paras)
    assert str(event.date_start) == "2023-01-01"  # untouched, even though it looks wrong


def test_apply_relative_date_fallback_leaves_unresolvable_dates_null():
    paras = [{"id": "p1", "text": "Earlier that week, nothing dated appears."}]
    event = _event(source_paragraph_ids=["p1"])
    merged = {"events": [event], "proposals": []}
    apply_relative_date_fallback(merged, paras)
    assert event.date_start is None


def test_prompt_states_written_vs_verbal_proposal_kind_rule():
    # Regression guard for the v7 rule: a written indication of interest
    # from the acquirer stays non_binding_indication even when it revises
    # an earlier number (this is exactly what P02/P03/P06 in the Splunk
    # gold set got wrong under the v5/v6 "first number vs. later number"
    # rule); a verbal revision from the acquirer is revised_bid; only the
    # target's own ask back is ever a counteroffer.
    instruction = extract.SYSTEM_INSTRUCTION
    assert "WRITTEN" in instruction
    assert "non_binding_indication" in instruction
    assert "even if it revises an earlier number" in instruction
    assert "VERBAL" in instruction
    assert "revised_bid" in instruction
    assert 'proposal_kind="counteroffer" is ONLY the target company' in instruction
