import time

import pytest
from google.genai import errors

from src import extract
from src.extract import (
    ExtractionError,
    _call_gemini,
    _is_daily_quota_exhausted,
    chunk_paragraphs_by_count,
    paragraph_anchor_dates,
    resolve_dates,
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


@pytest.fixture(autouse=True)
def isolate_session_calls():
    # _call_gemini appends to the module-level session call log on every
    # live call; reset it so one test's calls never leak into another's
    # running-total assertions.
    extract.reset_session_calls()
    yield
    extract.reset_session_calls()


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


# --- Vertex provider / cost logging --------------------------------------


def test_resolve_provider_defaults_to_aistudio(monkeypatch):
    monkeypatch.delenv("GEMINI_PROVIDER", raising=False)
    assert extract._resolve_provider() == "aistudio"


def test_resolve_provider_reads_env(monkeypatch):
    monkeypatch.setenv("GEMINI_PROVIDER", "vertex")
    assert extract._resolve_provider() == "vertex"


def test_compute_cost_is_zero_for_aistudio_regardless_of_model():
    usage = extract.Usage(prompt_tokens=1_000_000, output_tokens=1_000_000)
    assert extract._compute_cost_usd("aistudio", "gemini-3.5-flash", usage) == 0.0


def test_compute_cost_for_a_known_vertex_model():
    usage = extract.Usage(prompt_tokens=1_000_000, output_tokens=1_000_000)
    cost = extract._compute_cost_usd("vertex", "gemini-3.5-flash", usage)
    assert cost == pytest.approx(1.50 + 9.00)


def test_compute_cost_for_a_known_vertex_model_scales_with_tokens():
    usage = extract.Usage(prompt_tokens=500_000, output_tokens=0)
    cost = extract._compute_cost_usd("vertex", "gemini-3.5-flash", usage)
    assert cost == pytest.approx(0.75)


def test_compute_cost_is_unknown_not_zero_for_an_unpriced_vertex_model():
    usage = extract.Usage(prompt_tokens=1_000, output_tokens=1_000)
    assert extract._compute_cost_usd("vertex", "some-future-model", usage) is None


def test_compute_cost_for_gemini_3_6_flash_uses_conservative_rate():
    usage = extract.Usage(prompt_tokens=1_000_000, output_tokens=1_000_000)
    cost = extract._compute_cost_usd("vertex", "gemini-3.6-flash", usage)
    assert cost == pytest.approx(1.50 + 7.50)


def test_compute_cost_batch_mode_is_half_of_live_mode():
    usage = extract.Usage(prompt_tokens=1_000_000, output_tokens=1_000_000, thinking_tokens=500_000)
    live = extract._compute_cost_usd("vertex", "gemini-3.6-flash", usage, mode="live")
    batch = extract._compute_cost_usd("vertex", "gemini-3.6-flash", usage, mode="batch")
    assert batch == pytest.approx(live * 0.5)


def test_compute_cost_bills_thinking_tokens_at_the_output_rate():
    # Gemini 3.x's thinking models return reasoning tokens separately from
    # candidates_token_count, but Google bills them as output tokens --
    # a real call was observed with 5 candidates tokens and 299 thinking
    # tokens, so missing this would undercount real cost by ~60x.
    usage = extract.Usage(prompt_tokens=0, output_tokens=5, thinking_tokens=299)
    cost = extract._compute_cost_usd("vertex", "gemini-3.5-flash", usage)
    assert cost == pytest.approx((5 + 299) / 1_000_000 * 9.00)


class FakeUsageMetadataWithThinking:
    prompt_token_count = 56
    candidates_token_count = 5
    thoughts_token_count = 299
    total_token_count = 360


class FakeResponseWithThinking:
    model_version = "fake-model-version"
    usage_metadata = FakeUsageMetadataWithThinking()
    text = "{}"


def test_call_gemini_captures_and_bills_thinking_tokens(monkeypatch):
    monkeypatch.setenv("GEMINI_PROVIDER", "vertex")
    client = FakeClient([FakeResponseWithThinking()])
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    _, usage = _call_gemini("prompt", BackgroundExtraction, "gemini-3.5-flash")

    assert usage.thinking_tokens == 299
    call = extract._session_calls[0]
    assert call["thinking_tokens"] == 299
    assert call["cost_usd"] == pytest.approx((56 / 1_000_000) * 1.50 + ((5 + 299) / 1_000_000) * 9.00)


def test_call_gemini_passes_thinking_level_into_the_request_config(monkeypatch):
    from google.genai import types as genai_types

    captured_configs = []

    class SpyModels:
        def generate_content(self, **kwargs):
            captured_configs.append(kwargs["config"])
            return FakeResponse()

    class SpyClient:
        models = SpyModels()

    monkeypatch.setattr(extract, "_get_client", lambda: SpyClient())

    _call_gemini("prompt", BackgroundExtraction, "fake-model", thinking_level="low")

    assert captured_configs[0].thinking_config == genai_types.ThinkingConfig(thinking_level="LOW")


def test_call_gemini_leaves_thinking_config_unset_by_default(monkeypatch):
    captured_configs = []

    class SpyModels:
        def generate_content(self, **kwargs):
            captured_configs.append(kwargs["config"])
            return FakeResponse()

    class SpyClient:
        models = SpyModels()

    monkeypatch.setattr(extract, "_get_client", lambda: SpyClient())

    _call_gemini("prompt", BackgroundExtraction, "fake-model")

    assert captured_configs[0].thinking_config is None


def test_cache_key_differs_by_thinking_level():
    k_default = extract._cache_key([{"id": "p1", "text": "x"}], "m", BackgroundExtraction, None)
    k_low = extract._cache_key([{"id": "p1", "text": "x"}], "m", BackgroundExtraction, "low")
    assert k_default != k_low


def test_call_gemini_on_vertex_logs_a_session_call_with_cost(monkeypatch):
    monkeypatch.setenv("GEMINI_PROVIDER", "vertex")
    client = FakeClient([FakeResponse()])
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    _call_gemini("prompt", BackgroundExtraction, "gemini-3.5-flash")

    assert len(extract._session_calls) == 1
    call = extract._session_calls[0]
    assert call["provider"] == "vertex"
    assert call["model"] == "gemini-3.5-flash"
    assert call["prompt_tokens"] == 10
    assert call["output_tokens"] == 5
    assert call["cost_usd"] == pytest.approx((10 / 1_000_000) * 1.50 + (5 / 1_000_000) * 9.00)


def test_call_gemini_on_vertex_does_not_touch_the_aistudio_quota_file(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_PROVIDER", "vertex")
    quota_file = tmp_path / "quota_usage.json"
    monkeypatch.setattr(extract, "QUOTA_FILE", quota_file)
    client = FakeClient([FakeResponse()])
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    _call_gemini("prompt", BackgroundExtraction, "gemini-3.5-flash")

    assert not quota_file.exists()


def test_session_cost_summary_aggregates_across_calls(monkeypatch):
    monkeypatch.setenv("GEMINI_PROVIDER", "vertex")
    client = FakeClient([FakeResponse(), FakeResponse()])
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    _call_gemini("prompt", BackgroundExtraction, "gemini-3.5-flash")
    _call_gemini("prompt", BackgroundExtraction, "gemini-3.5-flash")

    summary = extract.session_cost_summary()
    assert summary["total_calls"] == 2
    assert summary["total_prompt_tokens"] == 20
    assert summary["total_output_tokens"] == 10
    assert summary["cost_unknown_for_some_calls"] is False
    assert summary["total_cost_usd"] == pytest.approx(2 * ((10 / 1_000_000) * 1.50 + (5 / 1_000_000) * 9.00))


def test_session_cost_summary_flags_unknown_pricing(monkeypatch):
    monkeypatch.setenv("GEMINI_PROVIDER", "vertex")
    client = FakeClient([FakeResponse()])
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    _call_gemini("prompt", BackgroundExtraction, "some-future-model")

    summary = extract.session_cost_summary()
    assert summary["cost_unknown_for_some_calls"] is True
    assert summary["total_cost_usd"] == 0  # unknown calls excluded, not treated as $0


def test_reset_session_calls_clears_the_log(monkeypatch):
    monkeypatch.setenv("GEMINI_PROVIDER", "vertex")
    client = FakeClient([FakeResponse()])
    monkeypatch.setattr(extract, "_get_client", lambda: client)
    _call_gemini("prompt", BackgroundExtraction, "gemini-3.5-flash")

    extract.reset_session_calls()

    assert extract.session_cost_summary()["total_calls"] == 0

    assert client.models.calls == 1


def test_per_minute_429_records_a_rate_limit_event(monkeypatch):
    before = time.time()
    monkeypatch.setattr(extract, "_rate_limit_events", [])
    client = FakeClient(
        [_quota_error(["GenerateRequestsPerMinutePerProjectPerModel-FreeTier"]), FakeResponse()]
    )
    monkeypatch.setattr(extract, "_get_client", lambda: client)

    _call_gemini("prompt", BackgroundExtraction, "fake-model")

    assert extract.rate_limit_events_since(before) == 1


def test_rate_limit_events_since_only_counts_events_after_the_cutoff(monkeypatch):
    monkeypatch.setattr(extract, "_rate_limit_events", [])
    extract.record_rate_limit_event()
    cutoff = time.time() + 1
    assert extract.rate_limit_events_since(cutoff) == 0


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


def test_resolve_dates_fills_relative_event_date_from_anchor():
    paras = [
        {"id": "p1", "text": "On August 30, 2023, the parties spoke."},
        {"id": "p2", "text": "Later that day, Robbins called Steele."},
    ]
    event = _event(source_paragraph_ids=["p2"])  # date_text="later that day"
    merged = {"events": [event], "proposals": []}
    resolve_dates(merged, paras)
    assert str(event.date_start) == "2023-08-30"
    assert str(event.date_end) == "2023-08-30"
    assert event.date_precision == "day"
    assert event.date_text == "later that day"  # original phrase untouched


def test_resolve_dates_fills_relative_proposal_date_from_anchor():
    paras = [
        {"id": "p1", "text": "On August 30, 2023, the parties spoke."},
        {"id": "p2", "text": "Later that day, Robbins called Steele with a new price."},
    ]
    proposal = _proposal(source_paragraph_ids=["p2"])  # date="later that day"
    merged = {"events": [], "proposals": [proposal]}
    resolve_dates(merged, paras)
    assert str(proposal.date_resolved) == "2023-08-30"
    assert proposal.date == "later that day"


def test_resolve_dates_leaves_unresolvable_dates_null():
    paras = [{"id": "p1", "text": "Earlier that week, nothing dated appears."}]
    event = _event(source_paragraph_ids=["p1"])
    proposal = _proposal(source_paragraph_ids=["p1"])
    merged = {"events": [event], "proposals": [proposal]}
    resolve_dates(merged, paras)
    assert event.date_start is None
    assert event.date_end is None
    assert proposal.date_resolved is None


def test_resolve_dates_does_not_touch_a_bare_month_date_text():
    # "January 2022" is an absolute but day-less date, not a relative
    # phrase -- _absolute_dates_in_text can't resolve it to a single day,
    # but it must NOT be treated as relative and sent through the anchor
    # fallback either (that would silently collapse a whole-month event
    # onto some unrelated day mentioned later in the same paragraph). This
    # is the exact regression caught while post-processing the v7 output:
    # an "advisor engagement, January 2022" event was wrongly collapsed
    # onto "January 23" (the NDA date mentioned later in the same
    # paragraph) before this case was excluded from the relative-phrase
    # fallback.
    paras = [
        {
            "id": "p1",
            "text": (
                "Also, in January 2022, the Board engaged Qatalyst Partners. "
                "On January 23, 2022, Cisco and Splunk signed a confidentiality agreement."
            ),
        }
    ]
    event = _event(
        date_text="January 2022",
        date_start="2022-01-01",
        date_end="2022-01-31",
        date_precision="month",
        source_paragraph_ids=["p1"],
    )
    merged = {"events": [event], "proposals": []}
    resolve_dates(merged, paras)
    assert str(event.date_start) == "2022-01-01"
    assert str(event.date_end) == "2022-01-31"
    assert event.date_precision == "month"


def test_resolve_dates_does_not_touch_a_shared_year_day_list():
    # "September 17, 18 and 19, 2023" has three days sharing one trailing
    # year -- _absolute_dates_in_text finds no "Month Day, Year" match in
    # it at all, but it is absolute information, not a relative phrase, so
    # it must be left alone rather than forced through the anchor fallback.
    paras = [
        {
            "id": "p1",
            "text": "The Committee met on September 17, 18 and 19, 2023 to provide guidance.",
        }
    ]
    event = _event(
        date_text="September 17, 18 and 19, 2023",
        date_start="2023-09-17",
        date_end="2023-09-19",
        date_precision="range",
        source_paragraph_ids=["p1"],
    )
    merged = {"events": [event], "proposals": []}
    resolve_dates(merged, paras)
    assert str(event.date_start) == "2023-09-17"
    assert str(event.date_end) == "2023-09-19"


def test_resolve_dates_overrides_whatever_the_model_put_when_own_text_is_absolute():
    # Date resolution is entirely code's job now -- even if the model
    # ignored the prompt and filled in a date_start of its own, a record
    # whose date_text is itself absolute must resolve to THAT date, not
    # whatever the model guessed.
    paras = [{"id": "p1", "text": "On August 30, 2023, the parties spoke."}]
    event = _event(
        date_text="August 30, 2023",
        source_paragraph_ids=["p1"],
        date_start="2023-01-01",
        date_precision="day",
    )
    merged = {"events": [event], "proposals": []}
    resolve_dates(merged, paras)
    assert str(event.date_start) == "2023-08-30"


def test_resolve_dates_handles_a_date_range_in_the_record_s_own_text():
    paras = [{"id": "p1", "text": "Representatives met several times between July 21, 2023, and August 3, 2023."}]
    event = _event(
        date_text="Between July 21, 2023, and August 3, 2023",
        source_paragraph_ids=["p1"],
    )
    merged = {"events": [event], "proposals": []}
    resolve_dates(merged, paras)
    assert str(event.date_start) == "2023-07-21"
    assert str(event.date_end) == "2023-08-03"
    assert event.date_precision == "range"


@pytest.mark.parametrize(
    "own_date, other_date, expected_iso",
    [
        ("December 17, 2021", "December 21, 2021", "2021-12-17"),
        ("June 20, 2023", "June 16, 2023", "2023-06-20"),
        ("August 25, 2023", "August 24, 2023", "2023-08-25"),
    ],
)
def test_resolve_dates_trusts_a_record_s_own_date_over_other_dates_in_the_same_paragraph(
    own_date, other_date, expected_iso
):
    # Regression guard for the exact failure class found in the v7 output:
    # a paragraph mentioning two absolute dates must never let the WRONG
    # one leak into a record whose own date_text/date already names the
    # right one. A naive "last date seen in the paragraph" anchor would
    # get this wrong; a record's own text must always win over the
    # paragraph-level anchor.
    paras = [
        {
            "id": "p1",
            "text": f"On {own_date}, Cisco proposed a price. Splunk followed up on {other_date}.",
        }
    ]
    event = _event(date_text=own_date, source_paragraph_ids=["p1"])
    proposal = _proposal(date=own_date, source_paragraph_ids=["p1"])
    merged = {"events": [event], "proposals": [proposal]}
    resolve_dates(merged, paras)
    assert str(event.date_start) == expected_iso
    assert str(event.date_end) == expected_iso
    assert str(proposal.date_resolved) == expected_iso


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


def test_prompt_no_longer_asks_the_model_to_resolve_dates():
    # v8: date resolution moved entirely into resolve_dates(); the model
    # must not be asked to attempt it (resolve_dates unconditionally
    # overrides anything it produces anyway, but an instruction telling it
    # to try is actively misleading now).
    instruction = extract.SYSTEM_INSTRUCTION
    assert "handled entirely in code" in instruction
    assert "do not attempt it" in instruction
    assert "Resolve it to an absolute date" not in instruction


def test_prompt_states_preview_of_proposal_is_a_discussion_event():
    instruction = extract.SYSTEM_INSTRUCTION
    assert '"discussion" Event, not a' in instruction
    assert "Only create a Proposal once the number is actually delivered" in instruction


def test_prompt_states_authorization_is_not_the_proposal():
    instruction = extract.SYSTEM_INSTRUCTION
    assert '"board_authorization" Event' in instruction
    assert "only when that counteroffer is actually conveyed to the other side" in instruction


def test_prompt_states_hedged_numbers_are_suggested_valuation():
    # v9 rule, regression guard for Zendesk gold P04/P08: "might be
    # prepared to offer" and "could be as high as" are hedges, not a
    # firm proposal, regardless of who said it or whether it revises an
    # earlier number.
    instruction = extract.SYSTEM_INSTRUCTION
    assert "HEDGED number is never a firm proposal" in instruction
    assert "may be able to offer" in instruction
    assert "could be as high as" in instruction
    assert "might be prepared to offer" in instruction
    assert 'proposal_kind="suggested_valuation"' in instruction


def test_prompt_reemphasizes_preview_vs_written_with_an_example():
    # v9: re-emphasizes the existing discussion-vs-proposal rule with a
    # concrete Zendesk-style example (a verbal preview followed by a
    # written proposal at the same price is ONE Proposal, not two).
    instruction = extract.SYSTEM_INSTRUCTION
    assert "verbally previews" in instruction
    assert "never two Proposals for the same number" in instruction


def test_prompt_restatement_rule_is_scoped_to_the_same_medium():
    # v11 fix, regression guard for Splunk gold P13/P14: the v10
    # "same bidder restating the same price is not a new Proposal" rule
    # was too broad and swallowed a real case -- Cisco's August 31, 2023
    # VERBAL $157 offer (p00490, a real Proposal, not a discussion/
    # preview -- unlike the v9 example above) followed by a WRITTEN
    # "revised non-binding indication of interest" at the same $157
    # (p00491). Both are real gold Proposals (P13 revised_bid, P14
    # non_binding_indication); v10 extracted only the first, treating
    # the written one as a mere restatement. The rule must only
    # suppress a restatement within the SAME medium (verbal->verbal or
    # written->written) -- a written delivery is always its own
    # Proposal, even when it repeats a price already given verbally.
    instruction = extract.SYSTEM_INSTRUCTION
    assert "NOT a new Proposal ONLY when it's" in instruction
    assert "SAME medium" in instruction
    assert "A WRITTEN indication of interest or proposal is ALWAYS its own Proposal" in instruction
    assert "even when it restates a price already conveyed VERBALLY" in instruction


def test_prompt_states_activist_event_type_rule():
    # v12: activist-shareholder actions (JANA Partners' campaign against
    # Zendesk -- letters, a proxy contest, nominations, settlement talks)
    # had no distinct event_type and were scattered across other/
    # discussion/nda; see data/benchmark/CHANGELOG.md for which gold
    # events moved. The rule must cover the activist's own actions even
    # when framed around the deal itself (e.g. demanding a sale), not
    # just generic activism unrelated to the transaction.
    instruction = extract.SYSTEM_INSTRUCTION
    assert 'event_type="activist"' in instruction
    assert "proxy contest" in instruction
    assert "director nomination" in instruction
    assert "settlement with an activist" in instruction
    assert "public campaign" in instruction
