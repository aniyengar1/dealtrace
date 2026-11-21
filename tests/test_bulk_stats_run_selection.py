import pytest

from src.bulk_stats import _resolve_run_id_for_deal
from src.load_db import upsert_deal, upsert_extraction_run

TEST_DEAL = {"deal_name": "Test Deal", "target": "Test Target", "acquirer": "Test Acquirer", "search_term": "test"}


@pytest.fixture()
def deal_id(db_conn):
    return upsert_deal(db_conn, "test_run_selection_deal", TEST_DEAL)


def _make_run(db_conn, deal_id, run_dir_suffix, days_ago):
    run_dir = f"2026010{days_ago}T000000Z_test_run_selection_deal_gemini-3.6-flash_{run_dir_suffix}"
    return upsert_extraction_run(db_conn, deal_id, "test_run_selection_deal", run_dir)


def test_resolve_run_id_returns_none_with_no_runs(db_conn, deal_id):
    assert _resolve_run_id_for_deal(db_conn, deal_id, "test_run_selection_deal") is None


def test_resolve_run_id_falls_back_to_latest_started_at(db_conn, deal_id):
    older = _make_run(db_conn, deal_id, "v9", 1)
    newer = _make_run(db_conn, deal_id, "v9-newer", 2)
    assert _resolve_run_id_for_deal(db_conn, deal_id, "test_run_selection_deal") == newer
    assert _resolve_run_id_for_deal(db_conn, deal_id, "test_run_selection_deal") != older


def test_resolve_run_id_prefers_prompt_lock_run_dir_over_latest(db_conn, deal_id, monkeypatch):
    # The locked run can be OLDER than the latest run -- Splunk's own
    # locked run is v11, even though a later v12 run also exists,
    # because v12 only added functionality unrelated to Splunk.
    locked_run_dir = "20260101T000000Z_test_run_selection_deal_gemini-3.6-flash_v9-locked"
    locked_id = upsert_extraction_run(db_conn, deal_id, "test_run_selection_deal", locked_run_dir)
    newer_id = _make_run(db_conn, deal_id, "v9-newer2", 2)

    import src.bulk_stats as bulk_stats_module

    monkeypatch.setitem(bulk_stats_module._PROMPT_LOCK_RUN_DIRS, "test_run_selection_deal", locked_run_dir)

    resolved = _resolve_run_id_for_deal(db_conn, deal_id, "test_run_selection_deal")
    assert resolved == locked_id
    assert resolved != newer_id
