from pathlib import Path

from src.discover import (
    FilingRow,
    base_form_type,
    extract_consideration,
    filter_relevant,
    group_into_deals,
    is_amendment,
    parse_form_index,
    quarters_from,
    _pick_primary_document,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mini_form.idx"


def test_parse_form_index_reads_every_data_row():
    rows = parse_form_index(FIXTURE)
    assert len(rows) == 7
    assert rows[0].form_type == "1-A"
    assert rows[0].company_name == "6d bytes inc."
    assert rows[0].cik == "1830909"
    assert rows[0].date_filed == "2022-05-23"
    assert rows[0].file_name == "edgar/data/1830909/0001477932-22-003739.txt"


def test_parse_form_index_handles_a_form_type_containing_a_space():
    rows = parse_form_index(FIXTURE)
    sc14d9 = [r for r in rows if r.cik == "1016169" and r.form_type == "SC 14D9"]
    assert len(sc14d9) == 1
    assert sc14d9[0].company_name == "ANTARES PHARMA, INC."


def test_filing_row_accession_properties():
    row = FilingRow("DEFM14A", "Anaplan, Inc.", "1540755", "2022-05-02", "edgar/data/1540755/0001193125-22-137023.txt")
    assert row.accession == "0001193125-22-137023"
    assert row.accession_nodash == "000119312522137023"


def test_base_form_type_strips_amendment_suffix():
    assert base_form_type("SC 14D9/A") == "SC 14D9"
    assert base_form_type("SC 14D9") == "SC 14D9"
    assert base_form_type("S-4/A") == "S-4"


def test_is_amendment():
    assert is_amendment("SC 14D9/A") is True
    assert is_amendment("SC 14D9") is False


def test_filter_relevant_keeps_only_target_forms_including_amendments():
    rows = parse_form_index(FIXTURE)
    relevant = filter_relevant(rows)
    form_types = {r.form_type for r in relevant}
    assert form_types == {"DEFM14A", "PREM14A", "SC 14D9", "SC TO-T", "SC 14D9/A"}
    assert "1-A" not in form_types
    assert "10-K" not in form_types


def test_quarters_from_spans_year_boundaries():
    quarters = quarters_from(2021, 4, 2022, 2)
    assert quarters == [(2021, 4), (2022, 1), (2022, 2)]


def test_group_into_deals_links_preliminary_proxy_to_definitive():
    rows = parse_form_index(FIXTURE)
    relevant = filter_relevant(rows)
    deals = group_into_deals(relevant)
    anaplan = next(d for d in deals if d.target_cik == "1540755")
    assert anaplan.primary.form_type == "DEFM14A"
    assert [f.form_type for f in anaplan.linked] == ["PREM14A"]


def test_group_into_deals_prefers_sc14d9_over_sc_to_t_and_links_amendment():
    rows = parse_form_index(FIXTURE)
    relevant = filter_relevant(rows)
    deals = group_into_deals(relevant)
    antares = next(d for d in deals if d.target_cik == "1016169")
    assert antares.primary.form_type == "SC 14D9"
    linked_types = sorted(f.form_type for f in antares.linked)
    assert linked_types == ["SC 14D9/A", "SC TO-T"]


def test_group_into_deals_splits_filings_more_than_a_year_apart():
    filings = [
        FilingRow("DEFM14A", "Old Deal Co.", "42", "2021-01-15", "edgar/data/42/0000000000-21-000001.txt"),
        FilingRow("DEFM14A", "Old Deal Co.", "42", "2023-06-01", "edgar/data/42/0000000000-23-000002.txt"),
    ]
    deals = group_into_deals(filings)
    assert len(deals) == 2


def test_group_into_deals_picks_primary_by_preference_not_date():
    # S-4 filed first, DEFM14A follows later in the same cluster -- DEFM14A
    # still wins primary despite not being chronologically first.
    filings = [
        FilingRow("S-4", "Merger Co.", "7", "2022-01-01", "edgar/data/7/0000000000-22-000001.txt"),
        FilingRow("DEFM14A", "Merger Co.", "7", "2022-03-01", "edgar/data/7/0000000000-22-000002.txt"),
    ]
    deals = group_into_deals(filings)
    assert len(deals) == 1
    assert deals[0].primary.form_type == "DEFM14A"
    assert deals[0].linked[0].form_type == "S-4"


def test_group_into_deals_prefers_bare_form_over_amendment_within_same_tier():
    filings = [
        FilingRow("DEFM14A/A", "Merger Co.", "7", "2022-02-01", "edgar/data/7/0000000000-22-000002.txt"),
        FilingRow("DEFM14A", "Merger Co.", "7", "2022-01-01", "edgar/data/7/0000000000-22-000001.txt"),
    ]
    deals = group_into_deals(filings)
    assert deals[0].primary.form_type == "DEFM14A"
    assert deals[0].linked[0].form_type == "DEFM14A/A"


def test_extract_consideration_finds_cash_from_merger_proxy_phrasing():
    html = "<p>you will be entitled to receive $81.00 in cash, without interest, for each share</p>"
    kind, value = extract_consideration(html)
    assert kind == "cash"
    assert value == 81.0


def test_extract_consideration_finds_cash_from_tender_offer_phrasing():
    html = "<p>$23.00 per share, net to the seller in cash, without interest</p>"
    kind, value = extract_consideration(html)
    assert kind == "cash"
    assert value == 23.0


def test_extract_consideration_finds_stock_exchange_ratio():
    html = "<p>each share converted into the right to receive 0.3521 shares of Acquirer common stock</p>"
    kind, value = extract_consideration(html)
    assert kind == "stock"
    assert value is None


def test_extract_consideration_finds_mixed():
    html = "<p>entitled to receive $10.00 in cash and 0.25 shares of Acquirer common stock for each share</p>"
    kind, value = extract_consideration(html)
    assert kind == "mixed"
    assert value == 10.0


def test_extract_consideration_ignores_authorized_share_count_boilerplate():
    # No decimal point -- an integer share count is not an exchange ratio.
    html = "<p>The company has authorized 500,000,000 shares of common stock</p>"
    kind, value = extract_consideration(html)
    assert kind == "unknown"
    assert value is None


def test_pick_primary_document_is_the_largest_non_index_htm():
    index_json = {
        "directory": {
            "item": [
                {"name": "0001-index.html", "size": ""},
                {"name": "0001.txt", "size": ""},
                {"name": "ny20003961x1_sc14d9.htm", "size": "745171"},
                {"name": "exhibit99.htm", "size": "1200"},
            ]
        }
    }
    assert _pick_primary_document(index_json) == "ny20003961x1_sc14d9.htm"


def test_pick_primary_document_returns_none_when_no_htm_present():
    index_json = {"directory": {"item": [{"name": "0001-index.html", "size": ""}]}}
    assert _pick_primary_document(index_json) is None
