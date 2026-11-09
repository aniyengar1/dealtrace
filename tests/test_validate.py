import pytest

from src import validate
from src.validate import (
    _run_id,
    check_dates_valid,
    check_low_le_high,
    check_numbers_in_quotes,
    check_quotes_in_paragraphs,
    dedupe_proposal_events,
    new_run_dir,
    normalize_for_match,
    normalize_whitespace,
)

LOOKUP = {
    "p1": "On January 15, 2022, Party B submitted an offer of $100.00 to $110.00 per share in cash.",
    "p2": "The Board of Directors met on January 20, 2022 to discuss the offer.",
}


def test_quote_matches_verbatim():
    ok, reason = check_quotes_in_paragraphs(
        ["submitted an offer of $100.00 to $110.00 per share"], ["p1"], LOOKUP
    )
    assert ok, reason


def test_quote_matches_across_whitespace_variation():
    # extra/irregular whitespace in the quote should still match after normalization
    ok, reason = check_quotes_in_paragraphs(
        ["submitted  an offer of \n $100.00 to $110.00   per share"], ["p1"], LOOKUP
    )
    assert ok, reason


def test_quote_not_found_fails():
    ok, reason = check_quotes_in_paragraphs(["this text is fabricated"], ["p1"], LOOKUP)
    assert not ok
    assert "not found" in reason


def test_quote_spanning_multiple_cited_paragraphs():
    ok, reason = check_quotes_in_paragraphs(
        ["cash. The Board of Directors met"], ["p1", "p2"], LOOKUP
    )
    assert ok, reason


def test_unknown_paragraph_id_fails():
    ok, reason = check_quotes_in_paragraphs(["anything"], ["p999"], LOOKUP)
    assert not ok
    assert "unknown paragraph id" in reason


def test_no_quotes_given_fails():
    ok, reason = check_quotes_in_paragraphs([], ["p1"], LOOKUP)
    assert not ok
    assert "no source_quotes given" in reason


def test_multiple_quotes_all_matching_passes():
    ok, reason = check_quotes_in_paragraphs(
        ["submitted an offer of $100.00 to $110.00 per share", "The Board of Directors met"],
        ["p1", "p2"],
        LOOKUP,
    )
    assert ok, reason


def test_one_of_multiple_quotes_not_found_fails():
    ok, reason = check_quotes_in_paragraphs(
        ["submitted an offer of $100.00 to $110.00 per share", "this part is fabricated"],
        ["p1", "p2"],
        LOOKUP,
    )
    assert not ok
    assert "this part is fabricated" in reason


def test_numbers_in_quotes_pass():
    record = {"price_low": 100.0, "price_high": 110.0}
    ok, reason = check_numbers_in_quotes(record, [LOOKUP["p1"]])
    assert ok, reason


def test_numbers_in_quotes_fails_on_fabricated_number():
    record = {"price_low": 100.0, "price_high": 999.0}
    ok, reason = check_numbers_in_quotes(record, [LOOKUP["p1"]])
    assert not ok
    assert "price_high" in reason


def test_numbers_in_quotes_handles_hyphenated_range_not_as_negative():
    # "4.0x-6.0x" must not be parsed as 4.0 and -6.0
    record = {"multiple_low": 4.0, "multiple_high": 6.0}
    ok, reason = check_numbers_in_quotes(record, ["a range of 4.0x-6.0x was applied"])
    assert ok, reason


def test_numbers_in_quotes_spread_across_separate_quotes_pass():
    # A record can satisfy the check with each number coming from a
    # different quote, not just one quote containing all of them.
    record = {"price_low": 100.0, "price_high": 110.0}
    ok, reason = check_numbers_in_quotes(
        record, ["an offer of $100.00 per share", "raised to $110.00 per share"]
    )
    assert ok, reason


def test_numbers_in_quotes_fails_when_missing_from_every_quote():
    record = {"price_low": 100.0, "price_high": 999.0}
    ok, reason = check_numbers_in_quotes(
        record, ["an offer of $100.00 per share", "discussed further on the call"]
    )
    assert not ok
    assert "price_high" in reason


def test_low_le_high_passes():
    ok, reason = check_low_le_high({"price_low": 100.0, "price_high": 110.0})
    assert ok, reason


def test_low_le_high_fails_when_inverted():
    ok, reason = check_low_le_high({"price_low": 110.0, "price_high": 100.0})
    assert not ok
    assert "price_low" in reason


def test_low_le_high_ignores_missing_fields():
    ok, reason = check_low_le_high({"price_low": 100.0, "price_high": None})
    assert ok, reason


def test_dates_valid_passes_with_no_dates():
    ok, reason = check_dates_valid({})
    assert ok, reason


def test_dates_valid_passes_with_ordered_range():
    ok, reason = check_dates_valid({"date_start": "2022-01-01", "date_end": "2022-01-15"})
    assert ok, reason


def test_dates_valid_fails_with_inverted_range():
    ok, reason = check_dates_valid({"date_start": "2022-01-15", "date_end": "2022-01-01"})
    assert not ok
    assert "after" in reason


def test_normalize_whitespace_collapses_runs():
    assert normalize_whitespace("a  \n b\t c") == "a b c"


def test_normalize_for_match_folds_curly_quotes_and_apostrophes():
    assert normalize_for_match("the ‘Agreement’") == "the 'Agreement'"
    assert normalize_for_match("the “Agreement”") == "the 'Agreement'"


def test_normalize_for_match_folds_single_and_double_quotes_to_one_canonical_char():
    # Single vs. double, curly vs. straight -- all four styles must collapse
    # onto the same character so a model swapping quote style around a span
    # doesn't register as a content difference.
    variants = ["the 'Agreement'", 'the "Agreement"', "the ‘Agreement’", "the “Agreement”"]
    normalized = {normalize_for_match(v) for v in variants}
    assert len(normalized) == 1


def test_normalize_for_match_folds_dash_variants():
    assert normalize_for_match("120.66–179.78") == "120.66-179.78"
    assert normalize_for_match("a — b") == "a - b"


def test_normalize_for_match_folds_nbsp_to_space():
    assert normalize_for_match("April 4, 2023") == "April 4, 2023"


def test_normalize_for_match_decodes_html_entities():
    assert normalize_for_match("the &#8220;Agreement&#8221;") == "the 'Agreement'"
    assert normalize_for_match("Cisco &amp; Splunk") == "Cisco & Splunk"


def test_quote_matches_despite_straight_vs_curly_quote_mismatch():
    # Filing text uses curly double quotes; the model quoted the same words
    # with plain ASCII quotes -- an equivalent encoding, not a real wording
    # difference, so this must still pass after normalization.
    lookup = {"p1": 'the “Confidentiality Agreement” was signed'}
    ok, reason = check_quotes_in_paragraphs(
        ['the "Confidentiality Agreement" was signed'], ["p1"], lookup
    )
    assert ok, reason


def test_quote_matches_despite_single_vs_double_quote_mismatch():
    # The real failure this guards against: the filing used curly double
    # quotes, but the model quoted the same span with curly single quotes --
    # a wrong-but-equivalent quote style, not a real wording difference.
    lookup = {"p1": "the “Confidentiality Agreement” was signed"}
    ok, reason = check_quotes_in_paragraphs(
        ["the ‘Confidentiality Agreement’ was signed"], ["p1"], lookup
    )
    assert ok, reason


def test_quote_matches_despite_dash_and_nbsp_variants():
    lookup = {"p1": "a range of 120.66–179.78 per share"}
    ok, reason = check_quotes_in_paragraphs(["120.66-179.78 per share"], ["p1"], lookup)
    assert ok, reason


def test_fuzzy_near_match_still_fails():
    # Normalization closes encoding gaps only -- an actual wording
    # difference must still fail, never pass via approximate matching.
    lookup = {"p1": "the Board of Directors convened a meeting on April 10, 2023"}
    ok, reason = check_quotes_in_paragraphs(
        ["the Board of Directors convened a meeting on April 9, 2023"], ["p1"], lookup
    )
    assert not ok
    assert "not found" in reason


def test_quote_matches_table_row_rendered_as_pipe_separated_cells():
    lookup = {"p1": "Sensitivity 1 Projections | 120.66–179.78\nSensitivity 2 Projections | 100.95–147.31"}
    ok, reason = check_quotes_in_paragraphs(
        ["Sensitivity 2 Projections | 100.95-147.31"], ["p1"], lookup
    )
    assert ok, reason


def _proposal_record(**overrides):
    base = {
        "date": "August 30, 2023",
        "price_low": 156.0,
        "price_high": 156.0,
    }
    base.update(overrides)
    return base


def _event_record(**overrides):
    base = {
        "event_type": "proposal",
        "date_start": "2023-08-30",
        "summary": "Robbins called Steele to convey a revised offer of $156 per share.",
        "source_quotes": ["a revised offer of $156 per share"],
    }
    base.update(overrides)
    return base


def test_dedupe_drops_event_matching_proposal_date_and_price():
    records = {
        "Event": [_event_record()],
        "Proposal": [_proposal_record()],
    }
    deduped, removed = dedupe_proposal_events(records)
    assert removed == 1
    assert deduped["Event"] == []
    assert len(deduped["Proposal"]) == 1


def test_dedupe_keeps_event_with_different_price():
    records = {
        "Event": [_event_record(summary="a revised offer of $160 per share", source_quotes=["$160 per share"])],
        "Proposal": [_proposal_record()],
    }
    deduped, removed = dedupe_proposal_events(records)
    assert removed == 0
    assert len(deduped["Event"]) == 1


def test_dedupe_keeps_event_with_different_date():
    records = {
        "Event": [_event_record(date_start="2023-08-31")],
        "Proposal": [_proposal_record()],
    }
    deduped, removed = dedupe_proposal_events(records)
    assert removed == 0
    assert len(deduped["Event"]) == 1


def test_dedupe_ignores_event_types_other_than_proposal_or_counteroffer():
    records = {
        "Event": [_event_record(event_type="board_meeting")],
        "Proposal": [_proposal_record()],
    }
    deduped, removed = dedupe_proposal_events(records)
    assert removed == 0
    assert len(deduped["Event"]) == 1


def test_dedupe_matches_counteroffer_event_type_too():
    records = {
        "Event": [_event_record(event_type="counteroffer")],
        "Proposal": [_proposal_record()],
    }
    deduped, removed = dedupe_proposal_events(records)
    assert removed == 1


def test_dedupe_uses_proposal_date_resolved_when_present():
    records = {
        "Event": [_event_record()],
        "Proposal": [_proposal_record(date="later that evening", date_resolved="2023-08-30")],
    }
    deduped, removed = dedupe_proposal_events(records)
    assert removed == 1


def _isolate_output_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(validate, "DATA_OUTPUT", tmp_path)
    monkeypatch.setattr(validate, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(validate, "LATEST_LINK", tmp_path / "latest")


def test_run_id_differs_by_deal_model_and_prompt_version():
    assert _run_id("splunk", "gemini-3.6-flash", "v6") != _run_id("zendesk", "gemini-3.6-flash", "v6")
    assert _run_id("splunk", "gemini-3.6-flash", "v6") != _run_id("splunk", "gemini-3-flash-preview", "v6")
    assert _run_id("splunk", "gemini-3.6-flash", "v6") != _run_id("splunk", "gemini-3.6-flash", "v7")


def test_new_run_dir_creates_folder_named_for_deal_model_and_prompt_version(tmp_path, monkeypatch):
    _isolate_output_dirs(tmp_path, monkeypatch)
    run_dir = new_run_dir("splunk", "gemini-3.6-flash", "v6")
    assert run_dir.is_dir()
    assert "splunk" in run_dir.name
    assert "gemini-3.6-flash" in run_dir.name
    assert "v6" in run_dir.name
    assert run_dir.parent == tmp_path / "runs"


def test_new_run_dir_points_latest_symlink_at_the_new_folder(tmp_path, monkeypatch):
    _isolate_output_dirs(tmp_path, monkeypatch)
    run_dir = new_run_dir("splunk", "gemini-3.6-flash", "v6")
    latest = tmp_path / "latest"
    assert latest.is_symlink()
    assert latest.resolve() == run_dir.resolve()


def test_new_run_dir_repoints_latest_to_each_new_run(tmp_path, monkeypatch):
    _isolate_output_dirs(tmp_path, monkeypatch)
    first = new_run_dir("splunk", "gemini-3.6-flash", "v6")
    # Force a distinct run id without depending on wall-clock granularity.
    monkeypatch.setattr(validate, "_run_id", lambda deal_slug, model, version: "second-run")
    second = new_run_dir("splunk", "gemini-3.6-flash", "v6")
    assert first != second
    assert first.exists()  # the earlier run's folder is never removed/overwritten
    assert (tmp_path / "latest").resolve() == second.resolve()


def test_new_run_dir_never_silently_overwrites_an_existing_run(tmp_path, monkeypatch):
    _isolate_output_dirs(tmp_path, monkeypatch)
    monkeypatch.setattr(validate, "_run_id", lambda deal_slug, model, version: "same-run-id")
    new_run_dir("splunk", "gemini-3.6-flash", "v6")
    with pytest.raises(FileExistsError):
        new_run_dir("splunk", "gemini-3.6-flash", "v6")
