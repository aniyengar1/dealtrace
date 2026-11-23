from copy import deepcopy
import json
import pytest
from earnings.hybrid.validation import validate
from earnings.hybrid.runner import calendar_for
from earnings.hybrid.prepare import DATA,read
from test_hybrid import fixture,cal

def comparison():
    d,docs=fixture();current=d['observations'][0];prior=deepcopy(current)
    current.update(status='raised',status_support='prior_range',prior_observation_index=1)
    prior.update(source_id='prior',status='unresolved',status_support='unresolved',prior_observation_index=None,issued_start='2026-05-19',issued_end='2026-05-19',center={'value':'2.30','scale':'1000000000'})
    text=docs[0]['canonical_text'].replace('2.40','2.30').replace('May20','May19')
    docs.append({**docs[0],'source_id':'prior','filed':'2026-05-19','canonical_text':text})
    for e in prior['evidence']:e.update(source_id='prior',quote=text,start=0,end=len(text))
    d['observations'].append(prior);return d,docs

def test_unknown_prior_status_does_not_invalidate_supported_prior_range():
    d,docs=comparison();before=deepcopy(d);a,b=validate(d,docs,cal)['observations']
    assert not a['deterministic_errors'] and a['resolved_status']=='raised'
    assert b['deterministic_errors']==['UNRESOLVED_STATUS'] and b['range_evidence_checks_passed']
    assert b['resolved_status']=='unresolved' and d==before
    assert a['quarantined'] and a['review_status']=='human_review_pending'

@pytest.mark.parametrize('fault',['metric','scope','currency','basis','period','quote','future','withdrawn','entity'])
def test_incompatible_or_unsupported_prior_still_blocks(fault):
    d,docs=comparison();p=d['observations'][1]
    if fault=='metric':p['metric_class']='arr'
    elif fault=='scope':p['scope']='segment'
    elif fault=='currency':p['currency']='other'
    elif fault=='basis':p['basis_kind']='constant_currency'
    elif fault=='period':p['period_end']='2026-07-30'
    elif fault=='quote':p['evidence'][0]['quote']='invented evidence'
    elif fault=='future':docs[1]['filed']='2026-05-21'
    elif fault=='withdrawn':p.update(status='withdrawn',center=None,tolerance=None,low=None,high=None,amount_style='none')
    elif fault=='entity':docs[1]['company']='DIFFERENT'
    assert validate(d,docs,cal)['observations'][0]['deterministic_errors']

def adi():
    required=[DATA/'run-20261114T032437489379Z.json',DATA/'pilot-1-input.json']
    if any(not p.is_file() for p in required):
        pytest.skip('Optional gitignored saved ADI diagnostic response/input unavailable; no inference fallback')
    run=read(DATA/'run-20261114T032437489379Z.json');r=next(i['result'] for i in run['results'] if i['case_id']=='pilot-1')
    docs=read(DATA/'pilot-1-input.json')['documents']
    return json.loads(r['text']),docs

def test_adi_partial_bound_resolves_only_from_registered_calendar():
    d,docs=adi();original=deepcopy(d);r=validate(d,docs,calendar_for('ADI'))['observations'][0]
    assert r['resolved_period_start']=='2024-08-04' and r['resolved_period_end']=='2024-11-02'
    assert 'CALENDAR_BOUNDARY_MISMATCH' not in r['deterministic_errors'] and r['deterministic_errors']==['UNRESOLVED_STATUS']
    assert d==original and r['proposal']['period_start'] is None
    assert 'PERIOD_RESOLVED_FROM_REGISTERED_CALENDAR_NOT_MODEL' in r['review_flags']

def test_conflicting_partial_bound_and_unknown_calendar_still_block():
    d,docs=adi();d['observations'][0]['period_end']='2024-11-03'
    assert 'CALENDAR_BOUNDARY_MISMATCH' in validate(d,docs,calendar_for('ADI'))['observations'][0]['deterministic_errors']
    def missing(*args):raise KeyError('No approved calendar')
    assert 'UNRESOLVED_FISCAL_CALENDAR' in validate(d,docs,missing)['observations'][0]['deterministic_errors']
