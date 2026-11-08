import pytest
from google.genai import errors

from src import extract
from src.extract import (
    ExtractionError,
    _call_gemini,
    _is_daily_quota_exhausted,
    chunk_paragraphs_by_count,
)
from src.schemas import BackgroundExtraction


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
