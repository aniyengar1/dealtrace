import re

from src.classify import _FIRST_FILER_RE, _SUBJECT_COMPANY_RE, classify_deal

TENDER_OFFER_HEADER = """<HTML><HEAD><TITLE>SEC EDGAR Submission</TITLE>
<!--
<SEC-HEADER>0001104659-21-054733.hdr.sgml : 20210426
<TYPE>SC TO-T
<SUBJECT-COMPANY>
<COMPANY-DATA>
<CONFORMED-NAME>General Finance CORP
<CIK>0001342287
<ASSIGNED-SIC>7359
</COMPANY-DATA>
</SUBJECT-COMPANY>
<FILED-BY>
<COMPANY-DATA>
<CONFORMED-NAME>UNITED RENTALS, INC.
<CIK>0001067701
<ASSIGNED-SIC>7359
</COMPANY-DATA>
</FILED-BY>
</SEC-HEADER>
-->
"""

PROXY_HEADER = """<HTML><HEAD><TITLE>SEC EDGAR Submission</TITLE>
<!--
<SEC-HEADER>0001193125-22-137023.hdr.sgml : 20220502
<TYPE>DEFM14A
<FILER>
<COMPANY-DATA>
<CONFORMED-NAME>Anaplan, Inc.
<CIK>0001540755
<ASSIGNED-SIC>7372
</COMPANY-DATA>
</FILER>
</SEC-HEADER>
-->
"""


def test_subject_company_regex_finds_the_tender_offer_target_not_the_bidder():
    match = _SUBJECT_COMPANY_RE.search(TENDER_OFFER_HEADER)
    assert match.group(1) == "1342287"
    assert match.group(2) == "7359"


def test_subject_company_regex_does_not_match_a_filer_only_header():
    assert _SUBJECT_COMPANY_RE.search(PROXY_HEADER) is None


def test_first_filer_regex_finds_the_proxy_filer():
    match = _FIRST_FILER_RE.search(PROXY_HEADER)
    assert match.group(1) == "1540755"
    assert match.group(2) == "7372"


def test_classify_deal_spac_by_sic_code():
    kind, reason = classify_deal("6770", None)
    assert kind == "spac_de_spac"
    assert "6770" in reason


def test_classify_deal_spac_by_text_requires_both_trust_and_blank_check_language():
    html = "<p>Funds held in the Trust Account will be used to fund this blank check company's business combination.</p>"
    kind, _ = classify_deal(None, html)
    assert kind == "spac_de_spac"


def test_classify_deal_trust_account_alone_is_not_enough():
    # An ordinary merger's escrow/trust arrangement shouldn't trip the
    # SPAC classifier just because the word "trust" appears.
    html = "<p>Funds will be held in a trust account pending closing of the merger.</p>"
    kind, _ = classify_deal("7372", html)
    assert kind != "spac_de_spac"


def test_classify_deal_debt_exchange():
    html = "<p>This exchange offer for the outstanding notes is being made pursuant to...</p>"
    kind, reason = classify_deal("7372", html)
    assert kind == "other"
    assert reason == "debt_or_warrant_exchange"


def test_classify_deal_reorganization():
    html = "<p>pursuant to the Agreement and Plan of Reorganization, dated as of...</p>"
    kind, reason = classify_deal("7372", html)
    assert kind == "other"
    assert reason == "reorganization"


def test_classify_deal_going_private_squeeze_out():
    html = "<p>the Merger is subject to Rule 13e-3 as a going-private transaction</p>"
    kind, reason = classify_deal("7372", html)
    assert kind == "other"
    assert reason == "going_private_squeeze_out"


def test_classify_deal_bank_holding_by_sic():
    kind, reason = classify_deal("6022", "<p>ordinary merger agreement language</p>")
    assert kind == "other"
    assert "6022" in reason


def test_classify_deal_defaults_to_public_company_acquisition():
    kind, reason = classify_deal("7372", "<p>Agreement and Plan of Merger between Acquirer and Target</p>")
    assert kind == "public_company_acquisition"
    assert reason == "default"


def test_classify_deal_with_no_sic_or_html_defaults_to_public_company_acquisition():
    kind, _ = classify_deal(None, None)
    assert kind == "public_company_acquisition"
