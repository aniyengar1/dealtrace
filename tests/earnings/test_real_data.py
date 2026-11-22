import json
from pathlib import Path
from datetime import date
from decimal import Decimal as D
import pytest
from earnings.registry import ROOT,companies,load_guidance
from earnings.actuals import parse_companyfacts
from earnings.engine import hurdle


@pytest.mark.parametrize('ticker',['PD','GTLB','ADBE','CRWD'])
def test_reconciled_sec_examples(ticker):
    gold=json.loads((ROOT/'reconciliation.json').read_text())[ticker]
    from earnings.verification import check_statement_columns
    check_statement_columns(gold)
    c=companies()[ticker]
    a=parse_companyfacts(c,gold['companyfacts']);g=[v for v in load_guidance(ticker) if v.metric=='consolidated_revenue']
    r=hurdle(c,a,g,date(2026,11,11))
    assert r.state=='ok'
    assert r.remaining_low==D(gold['expected_remaining_low'])
    assert r.remaining_high==D(gold['expected_remaining_high'])
    assert len(r.inputs)==5
    assert r.id==hurdle(c,list(reversed(a)),list(reversed(g)),date(2026,11,11)).id
    # Independent reported statement columns reconcile to the underlying XBRL inputs.
    for e in gold['statement_evidence']:
        assert e['unit']==('USD millions' if ticker=='ADBE' else 'USD thousands')
    assert g[0].original_verified and len(g)>=3
    assert (g[0].low,g[0].high)!=(g[-1].low,g[-1].high)


def test_all_approved_and_reporting_types():
    registry=companies();assert len(registry)==10
    for t,c in registry.items():
        gs=load_guidance(t);assert gs[0].original_verified
        assert c['annual_result']['type']=='Q4/FY annual-guidance outcome'
        assert ('Q4/FY' if t=='ADBE' else 'Q3') in c['next_report']['type']
    assert registry['CRM']['comparability']['blocked']
    assert any(g.status=='reaffirmed' for g in load_guidance('MDB'))
