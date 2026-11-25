from unittest.mock import patch

from src.deal_size import extract_merger_consideration, extract_shares_outstanding


def _with_text(text):
    return patch("src.deal_size._full_text", return_value=text)


def test_extracts_plain_record_date_share_count():
    text = "As of the Record Date, there were 150,476,816 shares of common stock outstanding and entitled to vote."
    with _with_text(text):
        result = extract_shares_outstanding("fake_slug", "Anaplan")
    assert result["value"] == 150476816


def test_filing_date_anchor_is_an_alternative_to_record_date():
    # Real shape: Coupa's own filing states the count as of the proxy
    # statement's own filing date, not a "record date" at all.
    text = "As of the date of the filing of this proxy statement, there were 75,541,300 shares of Company common stock outstanding."
    with _with_text(text):
        result = extract_shares_outstanding("fake_slug", "Coupa")
    assert result["value"] == 75541300


def test_present_tense_there_are_is_accepted():
    text = "As of the Record Date, there are 19,069,315 shares of Common Stock of the Company outstanding."
    with _with_text(text):
        result = extract_shares_outstanding("fake_slug", "MIRA")
    assert result["value"] == 19069315


def test_options_count_after_the_number_is_rejected():
    # Real shape: Anaplan -- an options/RSU count sentence matches every
    # other keyword, but is never the share count itself.
    text = (
        "As of the Record Date, there were 150,476,816 shares of common stock outstanding and entitled to vote. "
        "As of the Record Date, there were 4,425,144 outstanding options to acquire Anaplan common stock."
    )
    with _with_text(text):
        result = extract_shares_outstanding("fake_slug", "Anaplan")
    assert result["value"] == 150476816


def test_restricted_stock_units_count_is_rejected_even_though_it_says_shares():
    text = (
        "As of the Record Date, there were 150,476,816 shares of common stock outstanding and entitled to vote. "
        "As of the Record Date, there were 8,947,507 outstanding restricted stock units (rights to receive Anaplan shares)."
    )
    with _with_text(text):
        result = extract_shares_outstanding("fake_slug", "Anaplan")
    assert result["value"] == 150476816


def test_award_type_word_before_the_number_is_also_rejected():
    # Real shape: Confluent -- the award-type word precedes the number
    # here ("Confluent options covering...14,828,996 shares"), not the
    # reverse; checking only the window AFTER the number first missed this.
    text = (
        "As of the record date, there were 307,447,730 shares of our Class A common stock outstanding. "
        "As of January 5, 2026, there were outstanding Confluent options covering an aggregate of 14,828,996 shares of our common stock."
    )
    with _with_text(text):
        result = extract_shares_outstanding("fake_slug", "Confluent")
    assert result["value"] == 307447730


def test_units_is_accepted_for_lp_mlp_structures():
    # Real shape: EnLink Midstream, LLC -- an LP/MLP's equity instrument
    # is a "unit," not a "share."
    text = "As of the close of business on the Record Date, there were 457,079,545 outstanding EnLink Units."
    with _with_text(text):
        result = extract_shares_outstanding("fake_slug", "EnLink Midstream, LLC")
    assert result["value"] == 457079545


def test_hypothetical_illustrative_assumption_is_rejected():
    # Real shape: Uniti Group -- a pro-forma "for illustrative purposes
    # only, assume there are..." example is not a stated fact, even
    # though it otherwise matches the real share-count construction.
    text = (
        "On the Record Date, there were 244,229,237 Uniti Common Shares outstanding. "
        "For illustrative purposes only, assume there are 242,443,090 shares of Uniti Common Stock issued and outstanding immediately prior to Closing."
    )
    with _with_text(text):
        result = extract_shares_outstanding("fake_slug", "Uniti Group Inc.")
    assert result["value"] == 244229237


def test_prefers_record_date_anchor_over_filing_date_anchor_when_neither_names_target():
    # Real shape: Pioneer Energy Services / Patterson-UTI -- neither
    # sentence repeats the full company name, so the tie-break between
    # "record date" (this deal's own vote) and the looser "date of this
    # proxy statement" (which just as easily names the counterparty's
    # own count in the same joint filing) has to settle it.
    text = (
        "As of August 23, 2021, the last date before the date of this proxy statement/prospectus for which it was "
        "practicable to obtain this information, there were 189,038,970 shares of Patterson-UTI common stock outstanding. "
        "Outstanding Shares as of Record Date and Voting Rights of Pioneer Stockholders "
        "As of August 23, 2021, there were 1,822,670 shares of Pioneer common stock issued and outstanding, held by 79 holders of record."
    )
    with _with_text(text):
        result = extract_shares_outstanding("fake_slug", "PIONEER ENERGY SERVICES CORP")
    assert result["value"] == 1822670


def test_no_text_returns_none():
    with _with_text(""):
        assert extract_shares_outstanding("fake_slug", "Anaplan") is None


def test_no_matching_sentence_returns_none():
    with _with_text("Nothing relevant here at all."):
        assert extract_shares_outstanding("fake_slug", "Anaplan") is None


def test_extract_merger_consideration_reads_cash_per_share():
    # Real shape: Activision Blizzard/Microsoft.
    text = (
        "If the merger is completed, you will be entitled to receive $95.00 in cash, without interest, "
        "for each share of our common stock, par value $0.000001 per share, which we refer to as "
        "“Activision Blizzard common stock,” that you own."
    )
    with _with_text(text):
        result = extract_merger_consideration("fake_slug", "Activision Blizzard")
    assert result == {"type": "cash", "cash": 95.0, "ratio": None, "quote": result["quote"]}


def test_extract_merger_consideration_reads_stock_exchange_ratio():
    # Real shape: Denbury/ExxonMobil.
    text = (
        "If the Merger is completed, Denbury stockholders will receive, in exchange for each share of "
        "Denbury common stock, par value $0.001 per share, held immediately prior to the Merger, "
        "0.840 of a share of ExxonMobil common stock, without par value."
    )
    with _with_text(text):
        result = extract_merger_consideration("fake_slug", "DENBURY INC")
    assert result["type"] == "stock"
    assert result["ratio"] == 0.840
    assert result["cash"] is None


def test_extract_merger_consideration_rejects_hypothetical_example():
    # Real shape: ZAGG -- "if you own 100 shares... $420.00" is an
    # arithmetic multiple of the real $4.20 per-share price, not the
    # price itself.
    text = "For example, if you own 100 shares of ZAGG common stock, you will be entitled to receive $420.00 in cash in exchange for such shares."
    with _with_text(text):
        assert extract_merger_consideration("fake_slug", "ZAGG") is None


def test_extract_merger_consideration_rejects_equity_award_payout():
    # Real shape: Aris -- an RSU/PSU cash-out formula reads like a real
    # per-share consideration sentence but prices a different
    # instrument under its own conversion formula.
    text = (
        "Each outstanding Aris RSU Award will automatically become vested and cancelled and converted "
        "into the right to receive $7.00 in cash per restricted stock unit, for each share of Aris common stock."
    )
    with _with_text(text):
        assert extract_merger_consideration("fake_slug", "Aris") is None


def test_extract_merger_consideration_rejects_a_different_share_classs_own_ratio():
    # Real shape: Verde Bio/SSTC -- a Series C Preferred share class's
    # own conversion ratio ("0.15 shares of Verde Series C Preferred
    # Stock") sits in the same sentence as the real common-stock ratio,
    # but names the TARGET right after the number, not the acquirer.
    text = (
        "Each holder of Verde Series C Preferred Stock will be entitled to receive, for every 0.15 shares of "
        "Verde Series C Preferred Stock, one share of Class B preferred stock, par value $0.001 per share, of SSTC."
    )
    with _with_text(text):
        assert extract_merger_consideration("fake_slug", "Verde") is None


def test_extract_merger_consideration_returns_none_for_no_text():
    with _with_text(""):
        assert extract_merger_consideration("fake_slug", "Anaplan") is None
