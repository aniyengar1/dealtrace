from src.sanity import (
    check_event_dates_within_window,
    check_final_price_matches_consideration,
    check_has_at_least_one_proposal,
    check_signing_event_exists,
    extract_proxy_consideration,
    format_report,
    run,
)

COVER_PAGE_HTML = (
    "<p>If the Merger is completed, you will be entitled to receive "
    "$157.00 in cash, less any applicable withholding taxes, for each "
    "share of Splunk common stock that you own.</p>"
)


def test_extract_proxy_consideration_finds_the_real_phrase():
    assert extract_proxy_consideration(COVER_PAGE_HTML) == 157.00


def test_extract_proxy_consideration_handles_commas_in_large_prices():
    html = "<p>you will be entitled to receive $1,234.50 in cash for each share</p>"
    assert extract_proxy_consideration(html) == 1234.50


def test_extract_proxy_consideration_returns_none_when_phrase_absent():
    assert extract_proxy_consideration("<p>Nothing relevant here.</p>") is None


def test_final_price_matches_when_accepted_proposal_equals_consideration():
    records = {
        "Proposal": [
            {"date": "August 30, 2023", "price_low": 152.0, "price_high": 152.0, "status": "superseded"},
            {"date": "August 31, 2023", "price_low": 157.0, "price_high": 157.0, "status": "accepted"},
        ]
    }
    ok, detail = check_final_price_matches_consideration(records, 157.0)
    assert ok, detail


def test_final_price_falls_back_to_most_recent_when_none_accepted():
    records = {
        "Proposal": [
            {"date": "August 30, 2023", "price_low": 152.0, "price_high": 152.0, "status": "superseded"},
            {"date": "August 31, 2023", "price_low": 157.0, "price_high": 157.0, "status": "open"},
        ]
    }
    ok, detail = check_final_price_matches_consideration(records, 157.0)
    assert ok, detail


def test_final_price_flags_a_real_mismatch():
    records = {"Proposal": [{"date": "August 31, 2023", "price_low": 150.0, "price_high": 150.0, "status": "accepted"}]}
    ok, detail = check_final_price_matches_consideration(records, 157.0)
    assert not ok
    assert "150.00" in detail and "157.00" in detail


def test_final_price_flags_no_proposals():
    ok, detail = check_final_price_matches_consideration({"Proposal": []}, 157.0)
    assert not ok
    assert "no proposals" in detail


def test_final_price_flags_missing_proxy_consideration():
    records = {"Proposal": [{"date": "August 31, 2023", "price_low": 157.0, "price_high": 157.0, "status": "accepted"}]}
    ok, detail = check_final_price_matches_consideration(records, None)
    assert not ok
    assert "could not find" in detail


def test_signing_event_passes_when_both_parties_present():
    records = {
        "Event": [
            {"event_type": "signing", "parties": ["Cisco", "Splunk"]},
        ]
    }
    ok, detail = check_signing_event_exists(records, "Splunk", "Cisco")
    assert ok, detail


def test_signing_event_fails_when_no_signing_event():
    records = {"Event": [{"event_type": "board_meeting", "parties": ["Cisco", "Splunk"]}]}
    ok, detail = check_signing_event_exists(records, "Splunk", "Cisco")
    assert not ok
    assert "no signing event" in detail


def test_signing_event_fails_when_a_party_is_missing():
    records = {"Event": [{"event_type": "signing", "parties": ["Splunk"]}]}
    ok, detail = check_signing_event_exists(records, "Splunk", "Cisco")
    assert not ok


def test_event_dates_within_window_passes():
    records = {
        "Event": [
            {"event_type": "first_contact", "date_start": "2021-11-19", "date_end": "2021-11-19"},
            {"event_type": "signing", "date_start": "2023-09-20", "date_end": "2023-09-20"},
        ]
    }
    ok, detail = check_event_dates_within_window(records)
    assert ok, detail


def test_event_dates_within_window_flags_a_date_past_signing_plus_a_year():
    records = {
        "Event": [
            {"event_type": "first_contact", "date_start": "2021-11-19", "date_end": "2021-11-19"},
            {"event_type": "signing", "date_start": "2023-09-20", "date_end": "2023-09-20"},
            {"event_type": "other", "date_start": "2025-01-01", "date_end": "2025-01-01"},
        ]
    }
    ok, detail = check_event_dates_within_window(records)
    assert not ok
    assert "2025-01-01" in detail


def test_event_dates_within_window_fails_without_a_signing_event():
    records = {"Event": [{"event_type": "first_contact", "date_start": "2021-11-19", "date_end": "2021-11-19"}]}
    ok, detail = check_event_dates_within_window(records)
    assert not ok
    assert "no signing event" in detail


def test_has_at_least_one_proposal_passes_and_fails():
    ok, _ = check_has_at_least_one_proposal({"Proposal": [{}]})
    assert ok
    ok, detail = check_has_at_least_one_proposal({"Proposal": []})
    assert not ok
    assert "no proposals" in detail


def test_run_and_format_report_end_to_end():
    records = {
        "Event": [
            {"event_type": "first_contact", "date_start": "2021-11-19", "date_end": "2021-11-19", "parties": []},
            {"event_type": "signing", "date_start": "2023-09-20", "date_end": "2023-09-20", "parties": ["Cisco", "Splunk"]},
        ],
        "Proposal": [
            {"date": "September 20, 2023", "price_low": 157.0, "price_high": 157.0, "status": "accepted"},
        ],
    }
    results = run(records, COVER_PAGE_HTML, "Splunk", "Cisco")
    assert all(r["passed"] for r in results), results

    report = format_report("Cisco's Acquisition of Splunk", results)
    assert "Cisco's Acquisition of Splunk" in report
    assert report.count("[PASS]") == 4
    assert "[FLAG]" not in report
