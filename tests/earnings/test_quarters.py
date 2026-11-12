from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D
import json

import pytest
import psycopg
from psycopg import sql

from earnings import store
from earnings.actuals import parse_companyfacts
from earnings.engine import available_guidance, outcomes
from earnings.models import DateInterval, Policy
from earnings.quarters import METRIC, implied_growth, selected_outcome, prior_quarter
from earnings.registry import companies, load_guidance
from test_core import COMPANY, actual, guidance

DAY=date.fromisoformat
TARGET={'start':'2026-08-01','end':'2026-10-31','prior_start':'2025-08-01','prior_end':'2025-10-31',
        'available_on':'2026-08-01','growth_comparability':{'blocked':False,'available_on':'2026-08-01',
        'sources':['https://www.sec.gov/Archives/scope']}}


def quarter_guide(**changes):
    return replace(guidance(issued='2026-08-01',low='300',high='350'),
                   **{'start':DAY(TARGET['start']),'end':DAY(TARGET['end']),'metric':METRIC,**changes})


def prior(value='200', **changes):
    return replace(actual('2025-08-01','2025-10-31',value,'2025-12-01'),**changes)


def calc(facts=None, guides=None, cutoff='2026-11-11', target=None, policy=Policy()):
    return implied_growth(COMPANY,target or TARGET,facts if facts is not None else [prior()],
                          guides if guides is not None else [quarter_guide()],DAY(cutoff),policy)


def test_quarter_uses_entire_guidance_not_annual_ytd():
    ytd=actual('2026-02-01','2026-07-31','700','2026-09-01')
    r=calc([prior(),ytd])
    assert r.state=='ok' and (r.growth_low,r.growth_high)==(D('.5'),D('.75'))
    assert (r.guidance_low,r.guidance_high)==(D(300),D(350))
    assert r.inputs=={'guidance':quarter_guide().id,'prior_quarter':prior().id}
    assert not hasattr(r,'remaining_low')


def test_annual_and_quarter_selection_are_separate():
    annual=guidance();quarter=quarter_guide()
    assert available_guidance([annual,quarter],DAY('2026-11-11'),annual.start,annual.end,'TEST')==[annual]
    assert available_guidance([annual,quarter],DAY('2026-11-11'),quarter.start,quarter.end,'TEST',metric=METRIC)==[quarter]
    # Even a wrong annual metric with the same quarter boundaries cannot leak in.
    assert calc(guides=[replace(quarter,metric='consolidated_revenue')]).codes==('MISSING_PERIOD',)


def test_quarter_requires_both_availability_dates_and_conservative_interval():
    g=quarter_guide(filed=DAY('2026-11-12'))
    assert calc(guides=[g]).codes==('MISSING_PERIOD',)
    g=replace(g,filed=DAY('2026-11-01'),issued=DateInterval.read({'start':'2026-11-01','end':'2026-11-30','precision':'month'}))
    assert calc(guides=[g]).codes==('MISSING_PERIOD',)


def test_quarter_revisions_do_not_look_ahead():
    first=quarter_guide();revision=replace(first,low=D(320),filed=DAY('2026-11-12'),issued=DateInterval.read('2026-11-12'),status='raised',original_verified=False)
    revised_fact=prior('210',filed=DAY('2026-11-12'),accession='amendment')
    before=calc([prior(),revised_fact],[first,revision]);after=calc([prior(),revised_fact],[first,revision],cutoff='2026-11-12')
    assert before.growth_low==D('.5') and before.inputs['prior_quarter']==prior().id
    assert after.inputs['prior_quarter']==revised_fact.id and after.inputs['guidance']==revision.id
    assert before.id!=after.id


@pytest.mark.parametrize('kind,code',[('missing','MISSING_PERIOD'),('zero','ZERO_DENOMINATOR'),('basis','INCOMPARABLE_BASIS'),('withdrawn','GUIDANCE_WITHDRAWN'),('partial','MISSING_PERIOD')])
def test_quarter_blocks(kind,code):
    facts=[prior()];guides=[quarter_guide()]
    if kind=='missing':facts=[]
    if kind=='zero':facts=[prior('0')]
    if kind=='basis':facts=[prior(basis='organic')]
    if kind=='withdrawn':guides=[replace(guides[0],status='withdrawn',low=None,high=None,original_verified=False)]
    if kind=='partial':facts.append(actual('2026-08-01','2026-08-31','10','2026-09-15'))
    r=calc(facts,guides)
    assert r.codes==(code,) and r.growth_low is None


def test_quarter_guidance_freshness_boundary_and_no_prior_age_rule():
    issued=DAY('2026-11-11')-timedelta(days=150)
    g=quarter_guide(issued=DateInterval.read(str(issued)),filed=issued)
    assert calc(guides=[g]).state=='ok' # Old prior-year actual is intentional.
    r=calc(guides=[g],cutoff='2026-11-12')
    assert r.codes==('STALE_INPUT',) and 'guidance_days=150' in r.details[0]
    assert r.inputs['guidance']==g.id


def test_quarter_week_counts_not_normalized():
    target={**TARGET,'start':'2026-08-02','end':'2026-11-07','prior_start':'2025-08-03','prior_end':'2025-11-01'}
    c={**COMPANY,'calendar':'weeks'}
    g=quarter_guide(start=DAY(target['start']),end=DAY(target['end']))
    p=prior(start=DAY(target['prior_start']),end=DAY(target['prior_end']))
    r=implied_growth(c,target,[p],[g],DAY('2026-11-11'))
    assert r.codes==('INCOMPARABLE_BASIS',)
    target={**target,'end':'2026-10-31'};g=replace(g,end=DAY(target['end']))
    assert implied_growth(c,target,[p],[g],DAY('2026-11-11')).state=='ok'


def scored(value='300', *, g=None, cutoff='2026-12-02', review_changes=None, actual_changes=None, source_changes=None):
    g=g or quarter_guide();a=actual('2026-08-01','2026-10-31',value,'2026-12-02')
    a=replace(a,**(actual_changes or {}))
    review={'blocked':False,'available_on':'2026-12-02','actual_id':a.id,'guidance_id':g.id,
            'reason':'Result matches selected consolidated reported scope','sources':['https://www.sec.gov/Archives/result']}
    review.update(review_changes or {})
    return selected_outcome(COMPANY,TARGET,a,g,cutoff=DAY(cutoff),result_issued=DateInterval.read('2026-12-01'),
        result_source={'accession':'result','url':'https://www.sec.gov/Archives/result','filed_date':'2026-12-01',**(source_changes or {})},comparability=review)


@pytest.mark.parametrize('value,label',[('299','below'),('300','within'),('350','within'),('351','above')])
def test_quarter_selected_outcome_inclusive(value,label):
    r=scored(value);assert r['classification']==label and not r['codes']
    assert r['guidance']==quarter_guide().id


def test_point_guidance_has_no_implicit_tolerance():
    g=quarter_guide(high=D(300))
    assert scored('300',g=g)['classification']=='within'
    assert scored('300.01',g=g)['classification']=='above'


def test_growth_block_does_not_block_outcome_with_separate_evidence():
    t={**TARGET,'growth_comparability':{'blocked':True,'available_on':'2026-08-01','reason':'Acquisition ownership duration differs'}}
    assert calc(target=t).codes==('INCOMPARABLE_BASIS',)
    assert scored()['classification']=='within'
    assert scored(review_changes={'blocked':True,'reason':'Result recast excludes acquired business'})['classification']=='not_comparable'
    assert scored(review_changes={'actual_id':'another-version'})['classification']=='not_comparable'
    assert scored(review_changes={'available_on':'2026-12-03'})['classification']=='not_comparable'


def test_quarter_outcome_historical_availability_and_periods():
    assert scored(cutoff='2026-12-01')['codes']==['MISSING_PERIOD']
    assert scored(source_changes={'filed_date':'2026-12-03'})['codes']==['MISSING_PERIOD']
    assert scored(actual_changes={'start':DAY('2026-02-01')})['codes']==['MISSING_PERIOD']
    assert scored(g=quarter_guide(filed=DAY('2026-12-01')))['codes']==['MISSING_PERIOD']
    assert scored(actual_changes={'basis':'recast'})['classification']=='not_comparable'
    withdrawn=quarter_guide(status='withdrawn',low=None,high=None,original_verified=False)
    assert scored(g=withdrawn)['codes']==['GUIDANCE_WITHDRAWN']


def test_all_ten_quarter_targets_and_explicit_reaffirmation():
    for t,c in companies().items():
        target=c['quarter_targets'][-1]
        h=available_guidance(load_guidance(t),DAY('2026-11-11'),DAY(target['start']),DAY(target['end']),t,metric=METRIC)
        assert h[0].original_verified and h[0].metric==METRIC
        assert h[-1].status==('reaffirmed' if t=='MDB' else 'initial')
    assert len([g for g in load_guidance('CRM') if g.metric==METRIC])==1 # FY-only reaffirmation is not Q3.


def test_quarter_persistence_idempotency_and_public_access(db_conn):
    c={**COMPANY,'name':'Quarter test'};store.register(db_conn,c)
    g=quarter_guide();p=prior();store.save_guidance(db_conn,g);store.save_actual(db_conn,p)
    r=calc();assert store.save_quarter_calculation(db_conn,r,p)==1
    assert store.save_quarter_calculation(db_conn,r,p)==0
    row=db_conn.execute('SELECT growth_low,payload FROM earnings_quarter_calculations WHERE id=%s',(r.id,)).fetchone()
    assert row[0]==D('.5') and row[1]['inputs']['guidance']==g.id
    a=actual('2026-08-01','2026-10-31','300','2026-12-02');store.save_actual(db_conn,a)
    o=scored();assert store.save_quarter_outcome(db_conn,o)==1 and store.save_quarter_outcome(db_conn,o)==0
    for table in ['earnings_quarter_calculations','earnings_quarter_outcomes']:
        for role in ['anon','authenticated']:
            with db_conn.transaction():
                db_conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
                assert db_conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]>=1
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with db_conn.transaction():db_conn.execute(sql.SQL('DELETE FROM {}').format(sql.Identifier(table)))
            db_conn.execute('RESET ROLE')
    # Foreign keys do not permit a comparison from another company.
    other={**c,'ticker':'OTHER','cik':'0000000002'};store.register(db_conn,other)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with db_conn.transaction():
            store.save_quarter_calculation(db_conn,replace(r,company='OTHER'),p)


def test_quarter_change_attribution_tracks_guidance_and_comparison_versions():
    from earnings.quarters import attribution
    a=calc();b=calc([prior('210')],[quarter_guide(low=D(320))])
    assert attribution(a,b)==['guidance_changed','prior_comparison_changed']
    assert attribution(a,a)==['unchanged_inputs']
    with pytest.raises(ValueError):attribution(a,replace(a,target={**TARGET,'end':'2027-01-31'}))


def test_annual_outcome_uses_separate_growth_and_result_decisions():
    # An acquisition can change YoY scope while guidance and actual both include it.
    a=actual('2026-02-01','2027-01-31','1000000000','2027-03-20')
    c={**COMPANY,'comparability':{'blocked':True,'available_on':'2026-08-01','reason':'YoY acquisition scope differs'},
       'outcome_comparability':{'blocked':False,'available_on':'2027-03-20','sources':['https://www.sec.gov/Archives/result']}}
    kwargs={'cutoff':DAY('2027-03-20'),'result_issued':DateInterval.read('2027-03-10'),
            'result_source':{'accession':'result','url':'https://www.sec.gov/Archives/result','filed_date':'2027-03-10'}}
    assert outcomes(c,a,[guidance()],**kwargs)['latest']=='within'
    c['outcome_comparability']={**c['outcome_comparability'],'blocked':True,'reason':'Result recast excludes acquisition'}
    assert outcomes(c,a,[guidance()],**kwargs)['latest']=='not_comparable'


def test_comparability_evidence_must_be_sec_and_public_by_cutoff():
    assert scored(review_changes={'sources':['https://example.com/result']})['classification']=='not_comparable'
    r=scored(review_changes={'sources':[{'url':'https://www.sec.gov/Archives/result','filed_date':'2026-12-03'}]})
    assert r['classification']=='not_comparable' and 'unavailable' in r['details'][0]


def test_original_quarter_outcome_keeps_withdrawal_history():
    g=quarter_guide();a=actual('2026-08-01','2026-10-31','300','2026-12-02')
    withdrawn=replace(g,status='withdrawn',low=None,high=None,original_verified=False,
                      issued=DateInterval.read('2026-09-01'),filed=DAY('2026-09-01'))
    review={'blocked':False,'available_on':'2026-12-02','actual_id':a.id,'guidance_id':g.id,
            'sources':['https://www.sec.gov/Archives/result']}
    r=selected_outcome(COMPANY,TARGET,a,g,cutoff=DAY('2026-12-02'),result_issued=DateInterval.read('2026-12-01'),
        result_source={'accession':'result','url':'https://www.sec.gov/Archives/result','filed_date':'2026-12-01'},comparability=review,history=[g,withdrawn])
    assert r['classification']=='within' and r['selected_is_original']
    assert r['original_subsequently_withdrawn'] and not r['selected_is_latest_pre_result']
    assert r['latest_pre_result_status']=='withdrawn'
