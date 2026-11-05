from src.validate import (
    check_dates_valid,
    check_low_le_high,
    check_numbers_in_quote,
    check_quote_in_paragraphs,
    normalize_whitespace,
)

LOOKUP = {
    "p1": "On January 15, 2022, Party B submitted an offer of $100.00 to $110.00 per share in cash.",
    "p2": "The Board of Directors met on January 20, 2022 to discuss the offer.",
}


def test_quote_matches_verbatim():
    ok, reason = check_quote_in_paragraphs(
        "submitted an offer of $100.00 to $110.00 per share", ["p1"], LOOKUP
    )
    assert ok, reason


def test_quote_matches_across_whitespace_variation():
    # extra/irregular whitespace in the quote should still match after normalization
    ok, reason = check_quote_in_paragraphs(
        "submitted  an offer of \n $100.00 to $110.00   per share", ["p1"], LOOKUP
    )
    assert ok, reason


def test_quote_not_found_fails():
    ok, reason = check_quote_in_paragraphs("this text is fabricated", ["p1"], LOOKUP)
    assert not ok
    assert "not found" in reason


def test_quote_spanning_multiple_cited_paragraphs():
    ok, reason = check_quote_in_paragraphs(
        "cash. The Board of Directors met", ["p1", "p2"], LOOKUP
    )
    assert ok, reason


def test_unknown_paragraph_id_fails():
    ok, reason = check_quote_in_paragraphs("anything", ["p999"], LOOKUP)
    assert not ok
    assert "unknown paragraph id" in reason


def test_numbers_in_quote_pass():
    record = {"price_low": 100.0, "price_high": 110.0}
    ok, reason = check_numbers_in_quote(record, LOOKUP["p1"])
    assert ok, reason


def test_numbers_in_quote_fails_on_fabricated_number():
    record = {"price_low": 100.0, "price_high": 999.0}
    ok, reason = check_numbers_in_quote(record, LOOKUP["p1"])
    assert not ok
    assert "price_high" in reason


def test_numbers_in_quote_handles_hyphenated_range_not_as_negative():
    # "4.0x-6.0x" must not be parsed as 4.0 and -6.0
    record = {"multiple_low": 4.0, "multiple_high": 6.0}
    ok, reason = check_numbers_in_quote(record, "a range of 4.0x-6.0x was applied")
    assert ok, reason


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
