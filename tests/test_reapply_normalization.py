import json

import pytest

from src.load_db import content_hash, upsert_deal, upsert_event, upsert_extraction_run, upsert_proposal
from src.reapply_normalization import _find_loaded_run, _normalize_results, reapply_deal

# --- pure function: no DB needed -----------------------------------------

DEAL = {"target": "Target Inc", "acquirer": "Test Co", "party_map": {"Big Bank": "Target Inc"}}


def _result(record_type, record, passed=True, failure_reasons=None):
    return {"record_type": record_type, "record": record, "passed": passed, "failure_reasons": failure_reasons or []}


def test_normalize_results_resolves_generic_terms_in_events_and_proposals():
    results = [
        _result("Event", {"parties": ["Target Inc", "Board", "Parent"]}),
        _result("Proposal", {"proposer": "Buyer", "recipient": "Special Committee"}),
    ]
    normalized = _normalize_results(results, DEAL)
    assert normalized[0]["record"]["parties"] == ["Target Inc", "Target Inc", "Test Co"]
    assert normalized[1]["record"]["proposer"] == "Test Co"
    assert normalized[1]["record"]["recipient"] == "Target Inc"


def test_normalize_results_still_applies_the_per_deal_party_map():
    results = [_result("Proposal", {"proposer": "Big Bank", "recipient": "Target Inc"})]
    normalized = _normalize_results(results, DEAL)
    assert normalized[0]["record"]["proposer"] == "Target Inc"


def test_normalize_results_preserves_passed_and_failure_reasons():
    results = [_result("Event", {"parties": ["Board"]}, passed=False, failure_reasons=["x"])]
    normalized = _normalize_results(results, DEAL)
    assert normalized[0]["passed"] is False
    assert normalized[0]["failure_reasons"] == ["x"]


def test_normalize_results_is_a_no_op_on_already_resolved_values():
    results = [_result("Event", {"parties": ["Target Inc", "Test Co"]})]
    normalized = _normalize_results(results, DEAL)
    assert normalized[0]["record"]["parties"] == ["Target Inc", "Test Co"]


# --- DB-backed: reapply_deal ----------------------------------------------

TEST_DEAL = {
    "search_term": "target inc",
    "deal_name": "Test Co's Acquisition of Target Inc",
    "target": "Target Inc",
    "acquirer": "Test Co",
    "party_map": {},
}
TEST_RUN_DIR_NAME = "20200101T000000Z_test_deal_gemini-test-model_v1"


@pytest.fixture()
def deal_id(db_conn):
    return upsert_deal(db_conn, "test_deal", TEST_DEAL)


@pytest.fixture()
def run_id(db_conn, deal_id):
    return upsert_extraction_run(db_conn, deal_id, "test_deal", TEST_RUN_DIR_NAME)


@pytest.fixture()
def patched_deals(monkeypatch):
    import src.reapply_normalization as reapply_module

    monkeypatch.setitem(reapply_module.DEALS, "test_deal", TEST_DEAL)


@pytest.fixture()
def run_dir(tmp_path, monkeypatch, patched_deals):
    import src.reapply_normalization as reapply_module

    monkeypatch.setattr(reapply_module, "DATA_RUNS", tmp_path)
    d = tmp_path / TEST_RUN_DIR_NAME
    d.mkdir()
    return d


def test_find_loaded_run_returns_none_when_deal_has_no_run(db_conn):
    assert _find_loaded_run(db_conn, "no_such_deal") is None


def test_find_loaded_run_returns_the_run_id_and_dir_name(db_conn, run_id, run_dir):
    found = _find_loaded_run(db_conn, "test_deal")
    assert found == (run_id, TEST_RUN_DIR_NAME)


def test_reapply_deal_updates_event_parties_and_content_hash(db_conn, run_id, run_dir):
    stale_record = {"parties": ["Target Inc", "Parent"], "summary": "s"}
    upsert_event_record = dict(
        stale_record,
        date_text="January 1, 2022",
        date_start="2022-01-01",
        date_end="2022-01-01",
        date_precision="day",
        event_type="signing",
    )
    upsert_event(db_conn, run_id, upsert_event_record, passed=True, failure_reasons=[])
    old_hash = content_hash(upsert_event_record)

    extraction_path = run_dir / "test_deal_extraction.json"
    extraction_path.write_text(json.dumps([_result("Event", upsert_event_record)]))

    result = reapply_deal(db_conn, "test_deal")
    assert result["updated"]["Event"] == 1

    row = db_conn.execute(
        "SELECT parties, content_hash FROM events WHERE run_id = %s", (run_id,)
    ).fetchone()
    assert row[0] == ["Target Inc", "Test Co"]
    assert row[1] != old_hash

    on_disk = json.loads(extraction_path.read_text())
    assert on_disk[0]["record"]["parties"] == ["Target Inc", "Test Co"]


def test_reapply_deal_updates_proposal_proposer_and_recipient(db_conn, run_id, run_dir):
    proposal_record = {
        "date": "December 1, 2021",
        "date_resolved": None,
        "proposer": "Parent",
        "recipient": "Company",
        "price_low": 50.0,
        "price_high": 50.0,
        "premium_pct": None,
        "currency": "USD",
        "consideration_type": "cash",
        "proposal_kind": "non_binding_indication",
        "status": "accepted",
        "source_paragraph_ids": [],
        "source_quotes": [],
    }
    upsert_proposal(db_conn, run_id, proposal_record, passed=True, failure_reasons=[])

    extraction_path = run_dir / "test_deal_extraction.json"
    extraction_path.write_text(json.dumps([_result("Proposal", proposal_record)]))

    result = reapply_deal(db_conn, "test_deal")
    assert result["updated"]["Proposal"] == 1

    row = db_conn.execute(
        "SELECT proposer, recipient FROM proposals WHERE run_id = %s", (run_id,)
    ).fetchone()
    assert row[0] == "Test Co"
    assert row[1] == "Target Inc"


def test_reapply_deal_is_a_no_op_when_nothing_changes(db_conn, run_id, run_dir):
    record = {
        "parties": ["Target Inc", "Test Co"],
        "summary": "s",
        "date_text": "January 1, 2022",
        "date_start": "2022-01-01",
        "date_end": "2022-01-01",
        "date_precision": "day",
        "event_type": "signing",
    }
    upsert_event(db_conn, run_id, record, passed=True, failure_reasons=[])
    old_hash = content_hash(record)

    extraction_path = run_dir / "test_deal_extraction.json"
    extraction_path.write_text(json.dumps([_result("Event", record)]))

    result = reapply_deal(db_conn, "test_deal")
    assert result["updated"]["Event"] == 0

    row = db_conn.execute("SELECT content_hash FROM events WHERE run_id = %s", (run_id,)).fetchone()
    assert row[0] == old_hash


def test_reapply_deal_returns_none_run_dir_when_deal_has_no_loaded_run(db_conn, patched_deals):
    result = reapply_deal(db_conn, "test_deal")
    assert result == {"slug": "test_deal", "run_dir": None}
