import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.load_db import (
    content_hash,
    find_latest_run_dir,
    load_deal,
    load_extraction_run,
    load_paragraphs_from_sections,
    load_records_from_results,
    parse_run_dir_name,
    report_counts,
    upsert_deal,
    upsert_event,
    upsert_extraction_run,
    upsert_paragraph,
    upsert_proposal,
    upsert_valuation,
)

# --- pure functions: no DB needed ---------------------------------------


def test_parse_run_dir_name_splits_model_and_prompt_version():
    meta = parse_run_dir_name("coupa", "20261109T083517Z_coupa_gemini-3.6-flash_v9")
    assert meta["model"] == "gemini-3.6-flash"
    assert meta["prompt_version"] == "v9"
    assert meta["started_at"] == datetime(2026, 11, 9, 8, 35, 17, tzinfo=timezone.utc)


def test_parse_run_dir_name_handles_hyphenated_prompt_version():
    meta = parse_run_dir_name("splunk", "20261109T024628Z_splunk_gemini-3.6-flash_v8-rolenorm")
    assert meta["model"] == "gemini-3.6-flash"
    assert meta["prompt_version"] == "v8-rolenorm"


def test_parse_run_dir_name_handles_underscore_in_slug():
    # "new_relic" itself contains an underscore -- the slug must be matched
    # literally, not guessed by splitting on underscores.
    meta = parse_run_dir_name("new_relic", "20261109T081503Z_new_relic_gemini-3.6-flash_v9")
    assert meta["model"] == "gemini-3.6-flash"
    assert meta["prompt_version"] == "v9"


def test_parse_run_dir_name_rejects_a_mismatched_slug():
    with pytest.raises(ValueError):
        parse_run_dir_name("coupa", "20261109T083517Z_splunk_gemini-3.6-flash_v9")


def test_find_latest_run_dir_picks_the_most_recent_timestamp(tmp_path, monkeypatch):
    import src.load_db as load_db_module

    monkeypatch.setattr(load_db_module, "DATA_RUNS", tmp_path)
    (tmp_path / "20260101T000000Z_coupa_gemini-3.6-flash_v9").mkdir()
    (tmp_path / "20260201T000000Z_coupa_gemini-3.6-flash_v10").mkdir()
    (tmp_path / "20260115T000000Z_otherdeal_gemini-3.6-flash_v9").mkdir()

    result = find_latest_run_dir("coupa")
    assert result.name == "20260201T000000Z_coupa_gemini-3.6-flash_v10"


def test_find_latest_run_dir_returns_none_when_no_run_exists(tmp_path, monkeypatch):
    import src.load_db as load_db_module

    monkeypatch.setattr(load_db_module, "DATA_RUNS", tmp_path)
    assert find_latest_run_dir("nonexistent_deal") is None


def test_content_hash_is_stable_regardless_of_key_order():
    a = {"date_text": "January 1, 2022", "price_low": 10.0}
    b = {"price_low": 10.0, "date_text": "January 1, 2022"}
    assert content_hash(a) == content_hash(b)


def test_content_hash_differs_for_different_content():
    a = {"date_text": "January 1, 2022", "price_low": 10.0}
    b = {"date_text": "January 1, 2022", "price_low": 11.0}
    assert content_hash(a) != content_hash(b)


# --- DB-backed: deals, paragraphs, extraction_runs -----------------------

TEST_DEAL = {
    "deal_name": "Test Co's Acquisition of Target Inc",
    "target": "Target Inc",
    "acquirer": "Test Co",
    "search_term": "target inc",
}
TEST_RUN_DIR_NAME = "20200101T000000Z_test_deal_gemini-test-model_v1"


@pytest.fixture()
def deal_id(db_conn):
    return upsert_deal(db_conn, "test_deal", TEST_DEAL)


@pytest.fixture()
def run_id(db_conn, deal_id):
    return upsert_extraction_run(db_conn, deal_id, "test_deal", TEST_RUN_DIR_NAME)


def test_upsert_deal_is_idempotent_on_slug(db_conn, deal_id):
    again = upsert_deal(db_conn, "test_deal", TEST_DEAL)
    assert again == deal_id
    n = db_conn.execute("SELECT count(*) FROM deals WHERE slug = 'test_deal'").fetchone()[0]
    assert n == 1


def test_upsert_deal_updates_fields_in_place(db_conn, deal_id):
    changed = dict(TEST_DEAL, deal_name="A Renamed Deal")
    upsert_deal(db_conn, "test_deal", changed)
    name = db_conn.execute("SELECT deal_name FROM deals WHERE id = %s", (deal_id,)).fetchone()[0]
    assert name == "A Renamed Deal"


def test_upsert_paragraph_is_idempotent_on_deal_and_paragraph_id(db_conn, deal_id):
    upsert_paragraph(db_conn, deal_id, "p00001", "background_of_the_merger", None, "Original text.")
    upsert_paragraph(db_conn, deal_id, "p00001", "background_of_the_merger", None, "Original text.")
    n = db_conn.execute(
        "SELECT count(*) FROM paragraphs WHERE deal_id = %s AND paragraph_id = 'p00001'", (deal_id,)
    ).fetchone()[0]
    assert n == 1


def test_upsert_paragraph_updates_text_in_place(db_conn, deal_id):
    upsert_paragraph(db_conn, deal_id, "p00001", "background_of_the_merger", None, "Old text.")
    upsert_paragraph(db_conn, deal_id, "p00001", "background_of_the_merger", None, "New text.")
    text = db_conn.execute(
        "SELECT text FROM paragraphs WHERE deal_id = %s AND paragraph_id = 'p00001'", (deal_id,)
    ).fetchone()[0]
    assert text == "New text."


def test_upsert_extraction_run_is_idempotent_on_run_dir(db_conn, deal_id, run_id):
    again = upsert_extraction_run(db_conn, deal_id, "test_deal", TEST_RUN_DIR_NAME)
    assert again == run_id
    n = db_conn.execute("SELECT count(*) FROM extraction_runs WHERE run_dir = %s", (TEST_RUN_DIR_NAME,)).fetchone()[0]
    assert n == 1


# --- DB-backed: events / proposals / valuations --------------------------

SAMPLE_EVENT = {
    "date_text": "January 1, 2022",
    "date_start": "2022-01-01",
    "date_end": "2022-01-01",
    "date_precision": "day",
    "event_type": "signing",
    "parties": ["Target Inc", "Test Co"],
    "summary": "Test Co and Target Inc signed the merger agreement.",
    "source_paragraph_ids": ["p00001"],
    "source_quotes": ["signed the merger agreement"],
}

SAMPLE_PROPOSAL = {
    "date": "December 1, 2021",
    "date_resolved": None,
    "proposer": "Test Co",
    "recipient": "Target Inc",
    "price_low": 50.0,
    "price_high": 50.0,
    "premium_pct": None,
    "currency": "USD",
    "consideration_type": "cash",
    "proposal_kind": "non_binding_indication",
    "status": "accepted",
    "source_paragraph_ids": ["p00002"],
    "source_quotes": ["offer of $50.00 per share"],
}

SAMPLE_PREMIUM_ONLY_PROPOSAL = dict(
    SAMPLE_PROPOSAL,
    price_low=None,
    price_high=None,
    premium_pct=25.0,
    source_quotes=["a premium of approximately 25%"],
)

SAMPLE_VALUATION = {
    "advisor": "Test Bank LLC",
    "method": "dcf",
    "metric": "EV/Revenue",
    "multiple_low": 4.0,
    "multiple_high": 6.0,
    "implied_price_low": 40.0,
    "implied_price_high": 60.0,
    "key_assumptions": ["WACC of 10%"],
    "source_paragraph_ids": ["p00003"],
    "source_quotes": ["implied multiples of 4.0x to 6.0x"],
}


def test_upsert_event_round_trips_fields(db_conn, run_id):
    inserted = upsert_event(db_conn, run_id, SAMPLE_EVENT, passed=True, failure_reasons=[])
    assert inserted
    row = db_conn.execute(
        "SELECT date_start, date_precision, event_type, parties, review_status, passed "
        "FROM events WHERE run_id = %s",
        (run_id,),
    ).fetchone()
    assert row[0].isoformat() == "2022-01-01"
    assert row[1] == "day"
    assert row[2] == "signing"
    assert row[3] == ["Target Inc", "Test Co"]
    assert row[4] == "unreviewed"
    assert row[5] is True


def test_upsert_event_is_idempotent_on_run_and_content_hash(db_conn, run_id):
    first = upsert_event(db_conn, run_id, SAMPLE_EVENT, passed=True, failure_reasons=[])
    second = upsert_event(db_conn, run_id, SAMPLE_EVENT, passed=True, failure_reasons=[])
    assert first is True
    assert second is False
    n = db_conn.execute("SELECT count(*) FROM events WHERE run_id = %s", (run_id,)).fetchone()[0]
    assert n == 1


def test_reloading_never_clobbers_a_human_review_decision(db_conn, run_id):
    upsert_event(db_conn, run_id, SAMPLE_EVENT, passed=True, failure_reasons=[])
    db_conn.execute("UPDATE events SET review_status = 'confirmed' WHERE run_id = %s", (run_id,))

    upsert_event(db_conn, run_id, SAMPLE_EVENT, passed=True, failure_reasons=[])  # reload, same content

    status = db_conn.execute("SELECT review_status FROM events WHERE run_id = %s", (run_id,)).fetchone()[0]
    assert status == "confirmed"


def test_upsert_proposal_round_trips_premium_only_offer(db_conn, run_id):
    upsert_proposal(db_conn, run_id, SAMPLE_PREMIUM_ONLY_PROPOSAL, passed=True, failure_reasons=[])
    row = db_conn.execute(
        "SELECT price_low, price_high, premium_pct FROM proposals WHERE run_id = %s", (run_id,)
    ).fetchone()
    assert row[0] is None
    assert row[1] is None
    assert float(row[2]) == 25.0


def test_upsert_proposal_distinguishes_different_proposals_in_the_same_run(db_conn, run_id):
    upsert_proposal(db_conn, run_id, SAMPLE_PROPOSAL, passed=True, failure_reasons=[])
    upsert_proposal(db_conn, run_id, SAMPLE_PREMIUM_ONLY_PROPOSAL, passed=True, failure_reasons=[])
    n = db_conn.execute("SELECT count(*) FROM proposals WHERE run_id = %s", (run_id,)).fetchone()[0]
    assert n == 2


def test_upsert_valuation_round_trips_fields(db_conn, run_id):
    upsert_valuation(db_conn, run_id, SAMPLE_VALUATION, passed=True, failure_reasons=[])
    row = db_conn.execute(
        "SELECT advisor, method, key_assumptions FROM valuations WHERE run_id = %s", (run_id,)
    ).fetchone()
    assert row[0] == "Test Bank LLC"
    assert row[1] == "dcf"
    assert row[2] == ["WACC of 10%"]


def test_upsert_event_records_failure_reasons_for_a_failed_record(db_conn, run_id):
    upsert_event(
        db_conn, run_id, SAMPLE_EVENT, passed=False, failure_reasons=["source_quote(s) not found verbatim"]
    )
    row = db_conn.execute("SELECT passed, failure_reasons FROM events WHERE run_id = %s", (run_id,)).fetchone()
    assert row[0] is False
    assert row[1] == ["source_quote(s) not found verbatim"]


def test_load_records_from_results_counts_only_newly_inserted_rows(db_conn, run_id):
    results = [
        {"record_type": "Event", "record": SAMPLE_EVENT, "passed": True, "failure_reasons": []},
        {"record_type": "Proposal", "record": SAMPLE_PROPOSAL, "passed": True, "failure_reasons": []},
        {"record_type": "ValuationAnalysis", "record": SAMPLE_VALUATION, "passed": True, "failure_reasons": []},
    ]
    first = load_records_from_results(db_conn, run_id, results)
    assert first == {"Event": 1, "Proposal": 1, "ValuationAnalysis": 1}

    second = load_records_from_results(db_conn, run_id, results)
    assert second == {"Event": 0, "Proposal": 0, "ValuationAnalysis": 0}


# --- disk I/O wrappers: load_paragraphs_from_sections / load_extraction_run / load_deal ---


def test_load_paragraphs_from_sections_reads_every_section_file(tmp_path, monkeypatch, db_conn, deal_id):
    import src.load_db as load_db_module

    section_dir = tmp_path / "test_deal"
    section_dir.mkdir()
    (section_dir / "background_of_the_merger.json").write_text(
        json.dumps({"paragraphs": [{"id": "p00001", "text": "First paragraph.", "level": None}]})
    )
    (section_dir / "management_projections.json").write_text(
        json.dumps({"paragraphs": [{"id": "p00002", "text": "Second paragraph.", "level": None}]})
    )
    monkeypatch.setattr(load_db_module, "DATA_SECTIONS", tmp_path)

    n = load_db_module.load_paragraphs_from_sections(db_conn, deal_id, "test_deal")
    assert n == 2
    count = db_conn.execute("SELECT count(*) FROM paragraphs WHERE deal_id = %s", (deal_id,)).fetchone()[0]
    assert count == 2


def test_load_extraction_run_reads_the_runs_extraction_json(tmp_path, db_conn, deal_id):
    run_dir = tmp_path / TEST_RUN_DIR_NAME
    run_dir.mkdir()
    (run_dir / "test_deal_extraction.json").write_text(
        json.dumps(
            [{"record_type": "Event", "record": SAMPLE_EVENT, "passed": True, "failure_reasons": []}]
        )
    )

    result = load_extraction_run(db_conn, deal_id, "test_deal", run_dir)
    assert result == {"run_dir": TEST_RUN_DIR_NAME, "Event": 1, "Proposal": 0, "ValuationAnalysis": 0}


def test_load_deal_end_to_end_against_a_tmp_fixture(tmp_path, monkeypatch, db_conn):
    import src.load_db as load_db_module
    from src.run import DEALS

    monkeypatch.setitem(DEALS, "test_deal", TEST_DEAL | {"search_term": "target inc"})
    monkeypatch.setattr(load_db_module, "DATA_SECTIONS", tmp_path / "sections")
    monkeypatch.setattr(load_db_module, "DATA_RUNS", tmp_path / "runs")

    section_dir = tmp_path / "sections" / "test_deal"
    section_dir.mkdir(parents=True)
    (section_dir / "background_of_the_merger.json").write_text(
        json.dumps({"paragraphs": [{"id": "p00001", "text": "First paragraph.", "level": None}]})
    )

    run_dir = tmp_path / "runs" / TEST_RUN_DIR_NAME
    run_dir.mkdir(parents=True)
    (run_dir / "test_deal_extraction.json").write_text(
        json.dumps(
            [{"record_type": "Event", "record": SAMPLE_EVENT, "passed": True, "failure_reasons": []}]
        )
    )

    result = load_db_module.load_deal(db_conn, "test_deal")
    assert result["paragraphs"] == 1
    assert result["run_dir"] == TEST_RUN_DIR_NAME
    assert result["Event"] == 1


def test_report_counts_covers_every_table(db_conn, run_id):
    upsert_event(db_conn, run_id, SAMPLE_EVENT, passed=True, failure_reasons=[])
    counts = report_counts(db_conn)
    assert set(counts) == {"deals", "paragraphs", "extraction_runs", "events", "proposals", "valuations"}
    assert counts["events"] >= 1
