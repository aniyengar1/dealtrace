from dataclasses import replace
from datetime import date
from decimal import Decimal as D
import json
import pytest
import psycopg
from earnings.forecast import extrapolate, forecast, verdict
from earnings.metrics import parse_metrics, financial_overview
from earnings.evaluate import evaluate_case, evaluate
from earnings.product import build_report, save_report
from earnings.models import plain
from earnings.engine import hurdle
from earnings import store
from test_core import COMPANY, actual, guidance, facts


def test_forecast_and_benchmark(facts):
    r=hurdle(COMPANY,facts,[guidance()],date(2026,11,11));f=forecast(r,facts,[guidance()])
    assert f['estimate']==D('900000000') and f['benchmark']==D('900000000')
    assert f['verdict']=='miss' and f['status']=='experimental' and f['probabilities'] is None and f['interval'] is None
    assert f['inputs']==r.inputs and f['id']==forecast(r,facts,[guidance()])['id']
    assert extrapolate(D(600),D(500),D(1000))['estimate']==D(1200)
    assert extrapolate(D(600),D(500),D(1000))['benchmark']==D(1100)


@pytest.mark.parametrize('estimate,expected',[(D(9),'miss'),(D(10),'meet'),(D(11),'beat')])
def test_point_guidance(estimate,expected):
    assert verdict(estimate,D(10),D(10))==expected


def test_forecast_blocks(facts):
    for r in [hurdle(COMPANY,[],[guidance()],date(2026,11,11)),hurdle(COMPANY,facts,[guidance('withdrawn')],date(2026,11,11)),hurdle(COMPANY,facts,[guidance()],date(2027,4,1))]:
        f=forecast(r,facts,[guidance()]);assert f['status']=='blocked' and f['estimate'] is None
    c={**COMPANY,'comparability':{'blocked':True,'available_on':'2026-01-01','reason':'Acquisition unresolved'}}
    assert forecast(hurdle(c,facts,[guidance()],date(2026,11,11)),facts,[guidance()])['codes']==['INCOMPARABLE_BASIS']


def metric(key,concept,start,end,value,filed='2026-11-01',unit='USD'):
    return key,replace(actual(start,end,value,filed),concept=concept,unit=unit)


def test_metrics_exact_periods_accessions_and_no_eps_subtraction():
    c={**COMPANY,'period_start':'2026-02-01'}
    m=[metric('revenue','Revenues','2026-02-01','2026-10-31','700'),
       metric('revenue','Revenues','2026-08-01','2026-10-31','250'),
       metric('gross_profit','GrossProfit','2026-02-01','2026-10-31','350'),
       metric('operating_cash_flow','NetCashProvidedByUsedInOperatingActivities','2026-02-01','2026-10-31','100'),
       metric('capex','PaymentsToAcquirePropertyPlantAndEquipment','2026-02-01','2026-10-31','20'),
       metric('eps_diluted','EarningsPerShareDiluted','2026-02-01','2026-10-31','2.50',unit='USD/shares')]
    panels={p['type']:{x['key']:x for x in p['metrics']} for p in financial_overview(c,m,date(2026,11,11))}
    assert panels['ytd']['gross_margin']['value']=='0.5'
    assert panels['ytd']['free_cash_flow']['value']=='80'
    assert panels['ytd']['eps_diluted']['value']=='2.50'
    assert panels['quarter']['eps_diluted']['value'] is None
    assert panels['quarter']['operating_cash_flow']['value'] is None
    future=metric('net_income','NetIncomeLoss','2026-02-01','2026-10-31','999','2026-11-12')
    p=financial_overview(c,m+[future],date(2026,11,11))[1]
    assert next(x for x in p['metrics'] if x['key']=='net_income')['value'] is None
    # A value in another filing cannot be spliced into the margin calculation.
    bad=[(k,replace(a,accession='another') if k=='gross_profit' else a) for k,a in m]
    assert next(x for x in financial_overview(c,bad,date(2026,11,11))[1]['metrics'] if x['key']=='gross_margin')['value'] is None


CASE={'company':'TEST','forecast_date':'2025-11-01','period_start':'2025-02-01','period_end':'2026-01-31','ytd_end':'2025-10-31',
      'prior_start':'2024-02-01','prior_end':'2025-01-31','prior_ytd_end':'2024-10-31','scope_status':'reviewed','scope_sources':[{'filed_date':'2025-03-01'}]}


def test_evaluation_freezes_inputs_and_first_reported_outcome():
    a=[actual('2025-02-01','2025-10-31','700','2025-11-01'),
       actual('2024-02-01','2024-10-31','500','2024-11-01'),
       actual('2024-02-01','2025-01-31','1000','2025-03-01'),
       actual('2025-02-01','2026-01-31','1300','2026-03-01')]
    r=evaluate_case(CASE,COMPANY,a,date(2026,11,11));assert r['estimate']=='1400.0' and r['outcome']['value']=='1300'
    revised=[replace(a[0],value=D(900),filed=date(2026,4,1),accession='later'),replace(a[-1],value=D(2000),filed=date(2026,5,1),accession='restated')]
    later=evaluate_case(CASE,COMPANY,a+revised,date(2026,11,11))
    assert later['estimate']==r['estimate'] and later['outcome']==r['outcome']
    assert evaluate_case({**CASE,'scope_sources':[{'filed_date':'2026-01-01'}]},COMPANY,a,date(2026,11,11))['reason']=='SCOPE_EVIDENCE_NOT_PUBLIC'
    assert evaluate_case({**CASE,'scope_status':'unresolved'},COMPANY,a,date(2026,11,11))['status']=='blocked'
    assert evaluate_case(CASE,COMPANY,a,date(2026,2,1))['status']=='blocked'
    result=evaluate({'TEST':COMPANY},{'TEST':a},date(2026,11,11),[CASE])
    assert result['sample_size']==1 and result['coverage_denominator']==1 and result['interval_coverage'] is None
    assert result['status']=='insufficient_validation'


def test_report_asof_review_and_guidance_history(facts):
    c={**COMPANY,'name':'Test','fiscal_label':'FY2027','next_report':{'source_date':'2026-01-01'},'annual_result':{'source_date':'2026-01-01'}}
    gs=[guidance(),guidance('raised',low='1100000000',high='1150000000',issued='2026-11-12')]
    evaluation={'mae_usd':None,'mape':None,'benchmark_mae_usd':None,'benchmark_mape':None}
    report,calc=build_report(c,facts,[],gs,date(2026,11,11),evaluation,'sha','2026-11-11')
    assert len(report['guidance'])==1 and report['forecast']['status']=='experimental'
    r,_=build_report(c,facts,[],gs,date(2026,11,12),evaluation,'sha','2026-11-11')
    assert r['forecast']['codes']==['GUIDANCE_REVIEW_REQUIRED']


def test_product_persistence_and_rls(db_conn,facts):
    c={**COMPANY,'name':'Test','fiscal_label':'FY2027','next_report':{'source_date':'2026-01-01'},'annual_result':{'source_date':'2026-01-01'}}
    store.register(db_conn,c)
    for a in facts:store.save_actual(db_conn,a)
    store.save_guidance(db_conn,guidance())
    r,calc=build_report(c,facts,[],[guidance()],date(2026,11,11),{},'sha','2026-11-11')
    saved,count=save_report(db_conn,c,r,calc,facts);assert count==1
    assert save_report(db_conn,c,r,calc,facts)==(saved,0)
    row=db_conn.execute('SELECT forecast_estimate FROM earnings_company_reports WHERE id=%s',(r['id'],)).fetchone()
    assert row[0]==D('900000000')
    db_conn.execute('SET LOCAL ROLE anon')
    assert db_conn.execute('SELECT id FROM earnings_company_reports WHERE id=%s',(r['id'],)).fetchone()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db_conn.transaction():db_conn.execute('DELETE FROM earnings_company_reports WHERE id=%s',(r['id'],))
    db_conn.execute('RESET ROLE')


def test_insufficient_history_never_publishes_a_forecast(facts):
    facts[-1]=replace(facts[-1],value=D(0))
    r=hurdle(COMPANY,facts,[guidance()],date(2026,11,11));assert r.state=='ok'
    f=forecast(r,facts,[guidance()]);assert f['status']=='blocked' and f['codes']==['INSUFFICIENT_HISTORY']
    with pytest.raises(ValueError):extrapolate(D(100),D(0),D(200))


def test_evaluation_rejects_future_dates_and_fiscal_calendar_mismatch():
    assert evaluate_case(CASE,COMPANY,[],date(2024,1,1))['reason']=='FORECAST_DATE_AFTER_EVALUATION'
    assert evaluate({'TEST':COMPANY},{'TEST':[]},date(2024,1,1),[CASE])['cases']==[]
    a=[actual('2025-02-01','2025-10-31','700','2025-11-01'),actual('2024-02-01','2024-10-31','500','2024-11-01'),actual('2024-02-01','2025-01-31','1000','2025-03-01'),actual('2025-02-01','2026-01-31','1300','2026-03-01')]
    bad=evaluate_case({**CASE,'period_end':'2026-02-07'},{**COMPANY,'calendar':'weeks'},a,date(2026,11,11))
    assert bad['status']=='blocked' and 'fiscal-week' in bad['reason']


def test_refresh_records_source_gap_and_continues(monkeypatch,tmp_path,capsys):
    from earnings import product
    from src.fetch import FetchError
    monkeypatch.setattr(product,'companies',lambda:{'PD':{'cik':'0001568100'},'GTLB':{'cik':'0001653482'}})
    monkeypatch.setattr(product,'GAP_DIR',tmp_path)
    called=[]
    def update(t,*args):
        called.append(t)
        if t=='PD':raise FetchError('untrusted or private error text')
        return {'company':t,'new_report':0}
    monkeypatch.setattr(product,'refresh_company',update)
    result=product.refresh(['ALL'],date(2026,11,11),True)
    assert called==['PD','GTLB'] and result[0]['status']=='source_gap' and result[1]['company']=='GTLB'
    assert len(list(tmp_path.glob('*.json')))==1
    assert 'untrusted or private' not in capsys.readouterr().out


def test_week_mismatches_are_explicit_in_financial_overview():
    c={**COMPANY,'calendar':'weeks','period_start':'2026-02-02','period_end':'2027-01-31','comparison_ends':{}}
    m=[metric('revenue','Revenues','2025-02-03','2026-02-01','1000'),metric('revenue','Revenues','2024-01-29','2025-02-02','900')]
    growth=next(x for x in financial_overview(c,m,date(2026,11,11))[2]['metrics'] if x['key']=='revenue_growth')
    assert growth['value'] is None and growth['state']=='not_comparable' and 'fiscal-week' in growth['reason']


def test_metric_facts_keep_public_read_only_access(db_conn):
    from psycopg.types.json import Jsonb
    store.register(db_conn,{**COMPANY,'name':'Test'})
    a=actual('2026-02-01','2026-10-31','700')
    row={'id':a.id,'company_id':store.company_id('TEST'),'metric_key':'revenue','concept':a.concept,'period_start':a.start,'period_end':a.end,'filed_date':a.filed,'accession':a.accession,'unit':a.unit,'value':a.value,'payload':Jsonb(plain(a))}
    db_conn.execute('SET LOCAL ROLE service_role');assert store.insert(db_conn,'earnings_metric_facts',row)==1
    db_conn.execute('RESET ROLE');db_conn.execute('SET LOCAL ROLE anon')
    assert db_conn.execute('SELECT value FROM earnings_metric_facts WHERE id=%s',(a.id,)).fetchone()[0]==D(700)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with db_conn.transaction():db_conn.execute('UPDATE earnings_metric_facts SET value=0 WHERE id=%s',(a.id,))
    db_conn.execute('RESET ROLE')


def test_new_release_waits_for_actuals_without_lookahead(facts):
    c={**COMPANY,'name':'Test','fiscal_label':'FY2027','comparison_ends':{'2026-07-31':'2025-07-31'},'next_report':{'source_date':'2026-01-01'},'annual_result':{'source_date':'2026-01-01'}}
    old=[replace(facts[0],end=date(2026,7,31)),facts[1],replace(facts[2],end=date(2025,7,31))]
    release={'ytd_end':'2026-10-31','issued_date':'2026-11-11','filed_date':'2026-11-12','accession':'a','source_url':'https://www.sec.gov/Archives/release','period_quote':'reported through October 31, 2026'}
    r,_=build_report(c,old,[],[guidance()],date(2026,11,11),{},'sha','2026-11-12',release)
    assert r['forecast']['status']=='experimental' and r['latest_actual_release'] is None
    r,_=build_report(c,old,[],[guidance()],date(2026,11,12),{},'sha','2026-11-12',release)
    assert r['forecast']['status']=='blocked' and r['forecast']['codes']==['ACTUALS_PENDING_XBRL'] and r['forecast']['estimate'] is None
