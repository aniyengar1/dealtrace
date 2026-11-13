import json
from datetime import datetime, timedelta, timezone

import pytest

from src import bulk_run, extract
from src.schemas import BackgroundExtraction, ValuationExtraction


def _row(**overrides):
    base = {
        "id": "x",
        "target_cik": "123",
        "target_name": "Test Target",
        "primary_form_type": "DEFM14A",
        "primary_accession": "0001140361-23-022710",
        "primary_filed_date": "2023-05-03",
        "background_section_found": True,
        "background_word_count": 5000,
    }
    base.update(overrides)
    return base


# --- classify_for_queue -------------------------------------------------


def test_classify_for_queue_processes_a_normal_found_section():
    should_process, reason = bulk_run.classify_for_queue(_row())
    assert should_process is True
    assert reason == ""


def test_classify_for_queue_skips_when_section_not_found():
    should_process, reason = bulk_run.classify_for_queue(_row(background_section_found=False))
    assert should_process is False
    assert "not" in reason or "no" in reason.lower()


def test_classify_for_queue_skips_when_too_long():
    should_process, reason = bulk_run.classify_for_queue(_row(background_word_count=30000))
    assert should_process is False
    assert "25000" in reason or "too long" in reason


def test_classify_for_queue_processes_at_exactly_the_word_limit():
    should_process, _ = bulk_run.classify_for_queue(_row(background_word_count=25000))
    assert should_process is True


def test_classify_for_queue_processes_when_word_count_is_null_but_found():
    # Shouldn't happen in practice, but a null count must not crash the
    # length comparison or be treated as "too long".
    should_process, _ = bulk_run.classify_for_queue(_row(background_word_count=None))
    assert should_process is True


# --- path helpers ---------------------------------------------------------


def test_accession_nodash_strips_dashes():
    assert bulk_run._accession_nodash("0001140361-23-022710") == "000114036123022710"


def test_result_path_matches_the_discovery_scan_cache_naming(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk_run, "BULK_OUTPUT_DIR", tmp_path)
    path = bulk_run.result_path("1868044", "0001140361-23-022710")
    assert path.name == "1868044_000114036123022710.json"


def test_load_cached_html_reads_the_discovery_scan_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk_run, "DOC_CACHE_DIR", tmp_path)
    (tmp_path / "123_000114036123022710.html").write_text("<html>hi</html>")
    html = bulk_run.load_cached_html("123", "0001140361-23-022710")
    assert html == "<html>hi</html>"


def test_load_cached_html_returns_none_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk_run, "DOC_CACHE_DIR", tmp_path)
    assert bulk_run.load_cached_html("999", "0001-23-000000") is None


# --- spend cap / deadline -------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_session_calls():
    extract.reset_session_calls()
    yield
    extract.reset_session_calls()


def test_spend_cap_hit_is_false_with_no_calls_made():
    hit, reason = bulk_run.spend_cap_hit(260.0, 1.0)
    assert hit is False
    assert reason == ""


def test_spend_cap_hit_true_once_total_crosses_the_cap():
    extract._session_calls.append(
        {"provider": "vertex", "model": "gemini-3.6-flash", "mode": "live", "prompt_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cost_usd": 300.0}
    )
    hit, reason = bulk_run.spend_cap_hit(260.0, 1.0)
    assert hit is True
    assert "cap" in reason


def test_spend_cap_hit_applies_the_calibration_multiplier():
    extract._session_calls.append(
        {"provider": "vertex", "model": "gemini-3.6-flash", "mode": "live", "prompt_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cost_usd": 200.0}
    )
    # 200 * 1.0 is under a 260 cap, but 200 * 1.5 = 300 is over.
    assert bulk_run.spend_cap_hit(260.0, 1.0)[0] is False
    assert bulk_run.spend_cap_hit(260.0, 1.5)[0] is True


def test_spend_cap_hit_treats_unknown_pricing_as_a_hard_stop():
    extract._session_calls.append(
        {"provider": "vertex", "model": "some-future-model", "mode": "live", "prompt_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cost_usd": None}
    )
    hit, reason = bulk_run.spend_cap_hit(260.0, 1.0)
    assert hit is True
    assert "unknown" in reason.lower()


def test_deadline_hit_false_when_no_deadline_set():
    assert bulk_run.deadline_hit(None) is False


def test_deadline_hit_true_once_past():
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert bulk_run.deadline_hit(past) is True


def test_deadline_hit_false_when_still_ahead():
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert bulk_run.deadline_hit(future) is False


def test_batch_should_be_used_true_with_no_deadline():
    assert bulk_run.batch_should_be_used(None) is True


def test_batch_should_be_used_false_within_the_submit_margin():
    close_deadline = datetime.now(timezone.utc) + timedelta(hours=10)
    assert bulk_run.batch_should_be_used(close_deadline) is False


def test_batch_should_be_used_true_well_before_the_margin():
    far_deadline = datetime.now(timezone.utc) + timedelta(hours=48)
    assert bulk_run.batch_should_be_used(far_deadline) is True


# --- batch request body ---------------------------------------------------


def test_build_batch_request_body_matches_the_live_wire_shape():
    body = bulk_run._build_batch_request_body("hello", BackgroundExtraction, "gemini-3.6-flash")
    assert body["contents"] == [{"role": "user", "parts": [{"text": "hello"}]}]
    assert body["generationConfig"]["temperature"] == extract.GENERATION_TEMPERATURE
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    schema = body["generationConfig"]["responseSchema"]
    assert schema["type"] == "OBJECT"
    assert "events" in schema["properties"]
    assert "proposals" in schema["properties"]


def test_build_batch_request_body_differs_by_schema():
    bg = bulk_run._build_batch_request_body("x", BackgroundExtraction, "gemini-3.6-flash")
    val = bulk_run._build_batch_request_body("x", ValuationExtraction, "gemini-3.6-flash")
    assert bg["generationConfig"]["responseSchema"] != val["generationConfig"]["responseSchema"]


def test_write_batch_jsonl_wraps_each_request_under_a_request_key(tmp_path):
    requests = [{"a": 1}, {"a": 2}]
    out_path = tmp_path / "input.jsonl"
    bulk_run.write_batch_jsonl(requests, out_path)
    lines = out_path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"request": {"a": 1}}
    assert json.loads(lines[1]) == {"request": {"a": 2}}


# --- queue ordering (SQL shape, not DB-backed) -----------------------------


def test_queue_candidates_uses_db_conn(db_conn):
    # Smoke test against the real (test-transaction) DB -- just confirms
    # the query executes and returns the expected columns, not specific
    # rows (deal_candidates in the test DB may be empty).
    rows = bulk_run.queue_candidates(db_conn)
    assert isinstance(rows, list)
    if rows:
        assert set(bulk_run._CANDIDATE_COLUMNS) <= set(rows[0].keys())
