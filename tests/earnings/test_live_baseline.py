from copy import deepcopy
from dataclasses import replace
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal as D
from uuid import uuid4
import json
import pytest
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from earnings import baseline,history,store,live,score_live
from earnings.actuals import Blocked
from earnings.models import plain
from test_core import COMPANY,actual,guidance

NOW=datetime(2026,11,12,tzinfo=timezone.utc)

def rows(company='TEST',n=8):
    return [dict(id=str(uuid4()),company=company,period_start=f'2024-{i+1:02}-01',period_end=f'2024-{i+1:02}-28',
        outcome=('below','within','above')[i%3],status='eligible',recorded_at='2026-11-01T00:00:00+00:00',
        public_available_at='2025-01-01T00:00:00+00:00') for i in range(n)]

def test_rates_and_no_smoothing():
    r=baseline.probabilities('TEST',rows(),NOW)
    assert r['mode']=='company' and r['sample_size']==8
    assert r['probabilities']==dict(below=D('.375'),within=D('.375'),above=D('.25'))
    assert sum(r['probabilities'].values())==1
    assert baseline.brier(dict(below=D(1),within=D(0),above=D(0)),'above')==2
    assert baseline.brier(dict(below=D(1),within=D(0),above=D(0)),'below')==0
    with pytest.raises((ValueError,TypeError)):baseline.brier(dict(below=.5,within=.5,above=0),'above')

def test_pool_and_missing_history():
    r=baseline.probabilities('OTHER',rows()+rows('SECOND'),NOW)
    assert r['mode']=='pooled' and r['sample_size']==16 and r['company_sample_size']==0
    assert sum(r['probabilities'].values())==1
    with pytest.raises(Blocked):baseline.probabilities('OTHER',rows(),NOW)

def test_historical_selection_no_future_or_superseded_pass():
    r=rows(n=6);future=deepcopy(r[0]);future.update(id=str(uuid4()),status='blocked',outcome=None,recorded_at='2026-11-13T00:00:00+00:00')
    assert baseline.probabilities('TEST',r+[future],NOW)['sample_size']==6
    future['recorded_at']='2026-11-11T00:00:00+00:00'
    with pytest.raises(Blocked):baseline.probabilities('TEST',r+[future],NOW)
    r[0]['public_available_at']='2026-11-13T00:00:00+00:00'
    with pytest.raises(Blocked):baseline.probabilities('TEST',r,NOW)


def test_real_backfill_exact_versions_and_cutoffs():
    r=history.load_all()
    assert len(r)==80 and sum(x['status']=='eligible' for x in r)==75
    assert {x['company'] for x in r if x['status']=='blocked'}=={'CRWD','GTLB','MDB','OKTA','PD'}
    for x in r:
        s=x['source_record'];g=next(g for g in s['guidance_versions'] if g['id']==x['guidance_id'])
        assert g['filed']<=x['guidance_cutoff'] and g['issued']['end']<=x['guidance_cutoff']
        assert s['actual']['id']==x['actual_id']
        assert s['outcome_basis_review']['guidance_id']==g['id']
        assert s['result']['reported_revenue_quote'] and s['result']['accession']
        assert s['actual_filing_evidence']['url'].startswith('https://www.sec.gov/')
        if x['status']=='eligible':assert x['outcome'] in baseline.LABELS
    weeks=[x for x in r if x['company']=='LULU' and x['source_record']['target']['days']==98]
    assert len(weeks)==1 and weeks[0]['status']=='eligible'


def evidence(day):
    return dict(event_kind='results_release',verification_status='independently_verified',release_date=str(day),
        timezone='America/New_York',time_precision='after_close',source_url='https://official.example/announcement',
        checked_at=datetime.now(timezone.utc).isoformat())

def test_timing_date_only_before_open_and_call():
    e=evidence(date(2026,12,3));e['time_precision']='before_open'
    assert live.deadline(e)==datetime(2026,12,3,5,tzinfo=timezone.utc)
    e.update(time_precision='minute',timestamp_verified=True,release_timestamp='2026-12-03T16:00:00-05:00',timestamp_kind='results_publication',timestamp_source_quote='Results at 4pm Eastern')
    assert live.deadline(e).hour==21
    e['timestamp_kind']='earnings_call'
    with pytest.raises(Blocked):live.deadline(e)
    e['event_kind']='earnings_call'
    with pytest.raises(Blocked):live.deadline(e)


@pytest.fixture
def locked(db_conn):
    conn=db_conn;store.register(conn,{**COMPANY,'name':'Ledger transaction test'})
    now=conn.execute('SELECT clock_timestamp()').fetchone()[0].astimezone(timezone.utc)
    release=now.date()+timedelta(days=3);end=now.date()-timedelta(days=15);start=end-timedelta(days=89)
    g=replace(guidance(issued=str(now.date()-timedelta(days=90)),low='300',high='350'),start=start,end=end,metric='quarterly_consolidated_revenue')
    store.save_guidance(conn,g)
    conn.execute('SET LOCAL ROLE service_role')
    historical=rows()
    for r in historical:
        store.insert(conn,'earnings_historical_observations',dict(id=r['id'],company_id=store.company_id('TEST'),period_start=r['period_start'],period_end=r['period_end'],guidance_id=g.id,actual_id=str(uuid4()),status=r['status'],outcome=r['outcome'],public_available_at=baseline.aware(r['public_available_at']),payload=Jsonb(r)))
    obs=history.stored(conn);b=baseline.probabilities('TEST',obs,conn.execute('SELECT clock_timestamp()').fetchone()[0])
    e=evidence(release);check=dict(status='not_observed',checked_at=datetime.now(timezone.utc).isoformat(),target_start=str(start),target_end=str(end),sec={'success':True},official_ir={'success':True})
    target=dict(start=str(start),end=str(end))
    saved=live.insert_prediction(conn,COMPANY,target,g,b,e,check)
    return conn,g,b,e,check,target,saved


def test_db_clock_snapshot_duplicates_and_parallel_methods(locked):
    conn,g,b,e,check,target,saved=locked
    assert saved['made_at'] and saved['id']
    assert live.insert_prediction(conn,COMPANY,target,g,b,e,check) is None
    b={**b,'method_version':'parallel-test-v2'}
    assert live.insert_prediction(conn,COMPANY,target,g,b,e,check)['id']!=saved['id']
    snap=conn.execute('SELECT snapshot FROM earnings_live_predictions WHERE id=%s',(saved['id'],)).fetchone()[0]
    assert snap['locked_guidance']['id']==g.id and len(snap['historical_observations'])==8
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with conn.transaction():conn.execute('UPDATE earnings_live_predictions SET made_at=now() WHERE id=%s',(saved['id'],))
    # Snapshot survives a later mutable legacy source correction.
    conn.execute('RESET ROLE');conn.execute("UPDATE guidance_versions SET payload=payload || '{\"quote\":\"changed later\"}' WHERE id=%s",(g.id,))
    assert conn.execute('SELECT snapshot FROM earnings_live_predictions WHERE id=%s',(saved['id'],)).fetchone()[0]==snap


@pytest.mark.parametrize('table',['earnings_historical_observations','earnings_live_predictions','earnings_live_results'])
@pytest.mark.parametrize('operation',['UPDATE','DELETE','TRUNCATE'])
def test_db_application_mutation_denied(locked,table,operation):
    conn=locked[0]
    command=sql.SQL('UPDATE {} SET snapshot=snapshot').format(sql.Identifier(table)) if operation=='UPDATE' and table!='earnings_historical_observations' else sql.SQL('UPDATE {} SET payload=payload').format(sql.Identifier(table)) if operation=='UPDATE' else sql.SQL(('DELETE FROM' if operation=='DELETE' else operation)+' {}').format(sql.Identifier(table))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with conn.transaction():conn.execute(command)


def test_db_owner_truncate_trigger_and_no_backdating(locked):
    conn=locked[0];conn.execute('RESET ROLE')
    with pytest.raises(psycopg.Error,match='immutable'):
        with conn.transaction():conn.execute('TRUNCATE earnings_live_results')
    conn.execute('SET LOCAL ROLE service_role')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with conn.transaction():conn.execute('INSERT INTO earnings_live_predictions(made_at) VALUES (%s)',(NOW,))


def test_db_timing_already_public_and_forged_rates(locked):
    conn,g,b,e,check,target,saved=locked
    b={**b,'method_version':'parallel-test-v3'}
    for bad in [{**e,'release_date':str(date.today()-timedelta(days=1))},{**e,'event_kind':'earnings_call'}]:
        with pytest.raises((psycopg.Error,Blocked)):
            with conn.transaction():live.insert_prediction(conn,COMPANY,target,g,b,bad,check)
    with pytest.raises(psycopg.Error):
        with conn.transaction():live.insert_prediction(conn,COMPANY,target,g,b,e,{**check,'status':'already_public'})
    conn.execute('RESET ROLE')
    store.save_actual(conn,actual(target['start'],target['end'],'325',str(date.today())))
    conn.execute('SET LOCAL ROLE service_role')
    with pytest.raises(psycopg.Error,match='already present'):
        with conn.transaction():live.insert_prediction(conn,COMPANY,target,g,b,e,check)


def scoring_review(g,saved):
    made=baseline.aware(saved['made_at']);public=made+timedelta(microseconds=1)
    a=replace(actual(str(g.start),str(g.end),'325',str(made.date())),source_url='https://www.sec.gov/Archives/result')
    review=dict(actual={'id':a.id,**plain(a)},first_result_publication_lower_bound=public.isoformat(),actual_filing_accepted_at=public.isoformat(),evidence_available_at=public.isoformat(),
        result_source=dict(url='https://www.sec.gov/Archives/result',accession=a.accession,filed_date=str(made.date()),quote='Revenue results issued today'),
        outcome_basis_review=dict(actual_id=a.id,guidance_id=g.id,blocked=False,available_on=str(made.date()),sources=['https://www.sec.gov/Archives/result']))
    return review


def test_scoring_exact_lock_corrections_and_repeatability(locked):
    conn,g,b,e,check,target,saved=locked
    prediction=next(p for p in score_live.prediction_rows(conn) if p['id']==saved['id'])
    review=scoring_review(g,saved);now=conn.execute('SELECT clock_timestamp()').fetchone()[0]
    ev=score_live.evaluate(prediction,review,now)
    assert ev['outcome']=='within' and ev['brier']==baseline.brier(b['probabilities'],'within')
    first=score_live.save(conn,saved['id'],ev);assert first
    assert score_live.save(conn,saved['id'],ev) is None
    revised=deepcopy(review);a=store.actual_from({k:v for k,v in review['actual'].items() if k!='id'});a=replace(a,value=D(360),accession='amended-result')
    revised['actual']={'id':a.id,**plain(a)};revised['outcome_basis_review']['actual_id']=a.id
    later=score_live.save(conn,saved['id'],score_live.evaluate(prediction,revised,now))
    assert later['supersedes_id']==first['id']
    assert conn.execute('SELECT count(*) FROM earnings_live_results WHERE prediction_id=%s',(saved['id'],)).fetchone()[0]==2
    with pytest.raises(psycopg.Error,match='Incorrect'):
        with conn.transaction():score_live.save(conn,saved['id'],{**ev,'evidence_hash':'forged','brier':D(0)})
    review['first_result_publication_lower_bound']=saved['made_at']
    with pytest.raises(Blocked,match='Results could'):score_live.evaluate(prediction,review,now)


def test_publication_checks_fail_closed(monkeypatch,tmp_path):
    company={'ticker':'PD','cik':'0001568100'};target={'start':'2026-08-01','end':'2026-10-31','label':'Q3 FY2027'}
    filings={'form':['8-K'],'filingDate':['2026-11-01'],'items':['2.02'],'accessionNumber':['test']}
    monkeypatch.setattr(live,'fetch',lambda *a,**k:(json.dumps({'filings':{'recent':filings}}).encode(),{'url':'SEC'}))
    assert live.publication_check(company,target)['status']=='already_public_or_unresolved_sec_results'
    filings.update(form=[],filingDate=[],items=[],accessionNumber=[])
    class Response:
        status_code=200
        content=b'<h1>Loading</h1>'
    monkeypatch.setattr(live.requests,'get',lambda *a,**k:Response())
    monkeypatch.setattr(live,'CACHE',tmp_path)
    assert live.publication_check(company,target)['status']=='unverified'
    Response.content=b'<h2>November 12, 2026</h2><a>PagerDuty Reports Third Quarter Fiscal 2027 Financial Results</a>'
    assert live.publication_check(company,target)['status']=='already_public_or_unresolved_ir_results'
    Response.content=b'<h2>August 27, 2026</h2><a>PagerDuty Reports Second Quarter Fiscal 2027 Financial Results</a>'
    assert live.publication_check(company,target)['status']=='not_observed'


def test_changed_announcement_does_not_reuse_date(monkeypatch):
    monkeypatch.setattr(live,'check_source',lambda *a,**k:{'status':'confirmed','sha256':'changed'})
    with pytest.raises(Blocked,match='source body changed'):
        live.refresh_announcement({'ticker':'PD'},dict(source_url='official',announcement_issued_date='2026-11-01',release_date='2026-12-01',source_sha256='old'))


def test_history_ingestion_repeatability(db_conn):
    from earnings.registry import companies
    for c in companies().values():store.register(db_conn,c)
    db_conn.execute('SET LOCAL ROLE service_role')
    a=history.ingest(db_conn);b=history.ingest(db_conn)
    assert a['eligible']==75 and a['blocked']==5 and b['inserted']==0
    before=baseline.probabilities('PD',history.stored(db_conn),db_conn.execute('SELECT clock_timestamp()').fetchone()[0])
    assert before['sample_size']==7 and before['counts']=={'below':0,'within':3,'above':4}


def test_owner_rows_still_immutable(locked):
    conn=locked[0];conn.execute('RESET ROLE')
    for command in ['UPDATE earnings_live_predictions SET snapshot=snapshot','DELETE FROM earnings_live_predictions']:
        with pytest.raises(psycopg.Error,match='immutable'):
            with conn.transaction():conn.execute(command)


def test_retrospective_diagnostic_never_claims_live_and_excludes_later_inputs():
    from earnings.baseline_evaluation import run
    result=run();assert result['evaluation_kind']=='retrospective_reconstruction_NOT_live'
    assert result['evaluated_count']==57
    by_id={r['id']:r for r in history.load_all()}
    for r in result['evaluated']:
        assert r['baseline']['evaluation_kind']=='retrospective_reconstruction'
        for ident in r['baseline']['historical_ids']:
            assert baseline.aware(by_id[ident]['public_available_at'])<=baseline.aware(r['simulated_forecast_date'])
        assert r['id'] not in r['baseline']['historical_ids']


def test_score_source_verification_requires_real_quotes_and_day_boundaries(monkeypatch):
    from earnings.sec import fetch
    import earnings.sec
    # Source verification uses only fresh SEC transport, never IR financial values.
    a=actual('2026-08-01','2026-10-31','325','2026-12-02')
    a=replace(a,source_url='https://data.sec.gov/api/xbrl/companyfacts/CIK0000000001.json')
    payload={'facts':{'us-gaap':{'Revenues':{'units':{'USD':[dict(start=str(a.start),end=str(a.end),accn=a.accession,filed=str(a.filed),val=325)]}}}}}
    def fake(url,**kwargs):
        assert kwargs['refresh'] is True
        return (json.dumps(payload).encode() if '/companyfacts/' in url else b'<p>December 1, 2026 Revenue release</p>'),{}
    monkeypatch.setattr(earnings.sec,'fetch',fake)
    r=dict(actual={'id':a.id,**plain(a)},result_source=dict(url='https://www.sec.gov/Archives/release',quote='Revenue release',issued_date='2026-12-01',issuance_date_quote='December 1, 2026',filed_date='2026-12-01'),first_result_publication_lower_bound='2026-12-01T00:00:00-05:00',evidence_available_at='2026-12-03T00:00:00-05:00')
    score_live.verify_sources(r)
    bad=deepcopy(r);bad['result_source']['quote']='made up'
    with pytest.raises(Blocked,match='quote absent'):score_live.verify_sources(bad)
    bad=deepcopy(r);bad['first_result_publication_lower_bound']='2026-12-01T16:00:00-05:00'
    with pytest.raises(Blocked,match='start of the dated'):score_live.verify_sources(bad)
    bad=deepcopy(r);bad['evidence_available_at']='2026-12-02T00:00:00-05:00'
    with pytest.raises(Blocked,match='both day-precision'):score_live.verify_sources(bad)


def test_database_recomputes_frequency_probabilities(locked):
    conn,g,b,e,check,target,_=locked
    forged={**b,'probabilities':{'below':D('.5'),'within':D('.25'),'above':D('.25')}}
    with pytest.raises(psycopg.Error,match='Probabilities do not reproduce'):
        with conn.transaction():live.insert_prediction(conn,COMPANY,target,g,forged,e,check)


def test_database_rejects_future_history_inputs(locked):
    conn,g,b,e,check,target,_=locked
    r=rows(n=1)[0];r['public_available_at']=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    store.insert(conn,'earnings_historical_observations',dict(id=r['id'],company_id=store.company_id('TEST'),period_start='2023-01-01',period_end='2023-01-28',guidance_id=g.id,actual_id=str(uuid4()),status=r['status'],outcome=r['outcome'],public_available_at=baseline.aware(r['public_available_at']),payload=Jsonb({**r,'period_start':'2023-01-01','period_end':'2023-01-28'})))
    b={**b,'historical_ids':b['historical_ids']+[r['id']]}
    with pytest.raises(psycopg.Error,match='unavailable historical'):
        with conn.transaction():live.insert_prediction(conn,COMPANY,target,g,b,e,check)
