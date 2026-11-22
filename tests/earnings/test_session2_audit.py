"""Reproduce the frozen real-SEC audit and adjacent filing cutoffs without network.

Snapshots retain source hashes and exact reported statement columns. These tests
are deterministic reconciliation checks, not validation of forecast quality.
"""
from datetime import date
from decimal import Decimal as D
import json
from pathlib import Path

import pytest

from earnings.actuals import derive_remaining
from earnings.engine import hurdle, available_guidance, latest_guidance
from earnings.models import plain
from earnings.quarters import implied_growth, METRIC
from earnings.store import actual_from, guidance_from

ROOT=Path(__file__).resolve().parents[2]/'earnings'/'reports'
AUDIT=json.loads((ROOT/'audit_2026-11-12.json').read_text())
CUTOFFS=json.loads((ROOT/'audit_2026-11-12-cutoffs.json').read_text())


def actual(row):
    return actual_from({k:v for k,v in row.items() if k!='id'})


def guidance(row):
    return guidance_from({k:v for k,v in row.items() if k!='id'})


@pytest.mark.parametrize('ticker',list(AUDIT['companies']))
def test_real_twenty_row_audit_reproduces_exact_input_versions(ticker):
    row=AUDIT['companies'][ticker];c=row['company']
    facts={a['id']:actual(a) for a in row['actuals'].values() if not a['derivation']}
    # Only latest versions are needed for this frozen current-cutoff reproduction.
    guides=[guidance(row[k]) for k in ['annual_guidance','quarter_guidance']]
    cutoff=date.fromisoformat(AUDIT['as_of'])
    annual=hurdle(c,list(facts.values()),guides,cutoff)
    quarter=implied_growth(c,c['quarter_targets'][-1],list(facts.values()),guides,cutoff)
    assert plain(annual)==row['annual_calculation'] and annual.id==row['annual_calculation_id']
    assert plain(quarter)==row['quarter_calculation'] and quarter.id==row['quarter_calculation_id']
    assert (annual.state,quarter.state)==(('blocked','blocked') if ticker in ['CRM','OKTA','S'] else ('ok','ok'))
    if annual.state=='ok':
        parents=row['actuals'];remaining=derive_remaining(actual(parents['prior_annual']),actual(parents['prior_ytd']))
        assert remaining.id==annual.inputs['prior_remaining']
        assert remaining.value==D(parents['prior_remaining']['value'])
        assert annual.remaining_low==guides[0].low-actual(parents['ytd']).value
    if quarter.state=='ok':
        assert quarter.inputs['prior_quarter']==row['actuals']['prior_quarter']['id']
        assert 'actual_ytd' not in quarter.inputs and not hasattr(quarter,'remaining_low')


def test_all_actuals_reconcile_to_precise_reported_columns_and_scales():
    checks=AUDIT['reconciliations']
    assert len(checks)==42 and not AUDIT['discrepancies']
    for check in checks:
        document=AUDIT['documents'][check['source_url']]
        assert check['source_sha256']==document['sha256']
        assert any(row['quote']==check['quote'] for row in document['revenue_rows'])
        numbers=next(row['values'] for row in document['revenue_rows'] if row['quote']==check['quote'])
        reported=D(numbers[check['column_index']].replace(',',''))*D(check['scale'])
        assert reported==D(check['companyfacts_value'])==D(check['reported_value'])
        assert D(check['difference'])==D(check['discrepancy_pct'])==0
    # Every non-derived input used by an OK calculation has source reconciliation.
    reconciled={c['actual_id'] for c in checks if c['used_in_ok_calculation']}
    for row in AUDIT['companies'].values():
        if row['annual_calculation']['codes']:continue
        for a in row['actuals'].values():
            if not a['derivation']:assert a['id'] in reconciled


@pytest.mark.parametrize('ticker',['PD','MDB'])
def test_real_annual_and_quarter_cutoffs_exclude_later_information(ticker):
    case=CUTOFFS[ticker];c=case['company'];target=c['quarter_targets'][-1]
    facts=[actual(a) for a in case['actual_records']];guides=[guidance(g) for g in case['guidance_records']]
    for day,expected in case['dates'].items():
        cutoff=date.fromisoformat(day)
        annual=hurdle(c,facts,guides,cutoff)
        quarter=implied_growth(c,target,facts,guides,cutoff)
        assert annual.id==expected['annual']['id'] and annual.inputs==expected['annual']['inputs']
        assert quarter.id==expected['quarter']['id'] and quarter.inputs==expected['quarter']['inputs']
        eligible=available_guidance(guides,cutoff,date.fromisoformat(target['start']),date.fromisoformat(target['end']),ticker,metric=METRIC)
        assert [g.id for g in eligible]==expected['eligible_quarter_guidance_ids']
        assert all(g.filed<=cutoff and g.issued.end<=cutoff for g in eligible)
        assert all(a.filed<=cutoff for a in facts if a.id in annual.inputs.values())
    before,after=case['dates'].values()
    later={g['id'] for g in case['newly_available_guidance']}
    assert later.isdisjoint(set(before['annual']['inputs'].values())|set(before['quarter']['inputs'].values()))
    assert later.intersection(set(after['annual']['inputs'].values())|set(after['quarter']['inputs'].values()))
    # Do not backfill the November 11 review into an August/September quarter.
    assert after['quarter']['codes']==['INCOMPARABLE_BASIS']
    assert after['quarter']['growth_low'] is None


def test_salesforce_combined_block_does_not_predate_its_october_evidence():
    review=AUDIT['companies']['CRM']['company']['comparability']
    assert review['available_on']=='2026-10-20'
    assert all(source['filed_date']<=review['available_on'] for source in review['sources'])
    assert any(source['filed_date']=='2026-10-20' for source in review['sources'])


def test_date_access_failures_do_not_acquire_invented_fetch_times():
    dates=json.loads((ROOT/'audit_2026-11-12-date-checks.json').read_text())
    for check in dates['direct_http']:
        assert check['checked_at']
        if check.get('http_status')!=200:assert check['fetched_at'] is None
    for observed in dates['indexed_official_date_observations']:
        assert observed['observed_at'] and observed['fetched_at'] is None
