from copy import deepcopy
from datetime import datetime,date,timedelta,timezone
from dataclasses import replace
from uuid import uuid4
from pathlib import Path
import json
import pytest
import psycopg
from psycopg.types.json import Jsonb
from earnings import current_checks as checks,live,store,history,baseline,smoothed_baseline
from earnings.registry import companies
from earnings.models import record_id
from earnings.actuals import Blocked
from test_live_baseline import rows
from test_core import guidance

def data_for(c,e,clock):
    target=c['quarter_targets'][-1];stamp=(clock-timedelta(seconds=30)).isoformat()
    return {'company':c['ticker'],'announcement_id':e['id'],'observer':'Synthetic owner fixture, not real human review',
        'timezone':'UTC','precision':'second','personally_checked':True,'contradictions':[],
        'attestation':'Synthetic test: personally checked all listed pages and complete target-period coverage; not a real attestation.',
        'automation_gap':{'url':e['source_url'],'reason':'Synthetic automation403','provenance':'owner_reported'},
        'pages':[{'url':e['source_url'],'checked_at':stamp,'roles':['schedule'],'coverage':'Full dated announcement, results wording and schedule','complete':True},
            {'url':'https://investor.okta.com/news-and-events/news-releases/default.aspx','checked_at':stamp,'roles':['news_inventory'],'coverage':'All pages since target start including preliminary results','complete':True},
            {'url':'https://investor.okta.com/financials/quarterly-results/default.aspx','checked_at':stamp,'roles':['results_inventory'],'coverage':'Current target-year results list and linked releases','complete':True}],
        'schedule':{**{k:e.get(k) for k in ('release_date','timezone','time_precision','release_time')},'event_kind':'results_release'},
        'publication':{'status':'not_observed','target_start':target['start'],'target_end':target['end'],
            'coverage_from':target['start'],'coverage_through':clock.date().isoformat(),'preliminary_results_checked':True,'pagination_complete':True}}

def sealed(data,c,e,clock):
    r={'policy_version':checks.POLICY,'data':data,'input_sha256':'a'*64,'ingested_at':clock.isoformat(),'assessment':checks.assess(data,c,e,clock)}
    r['id']=record_id('owner-current-check-v2',r);return r

def fixture():
    c=companies()['OKTA'];e=live.announcement(c);clock=datetime(2026,11,17,5,tzinfo=timezone.utc)
    return c,e,clock,data_for(c,e,clock)

def test_complete_current_check_keeps_durable_retrieval_unchanged():
    c,e,clock,d=fixture();before=deepcopy(e);r=sealed(d,c,e,clock)
    assert checks.validate_record(r,c,e,clock)['status']=='usable' and e==before
    assert r['assessment']['checked_at']==d['pages'][0]['checked_at']

@pytest.mark.parametrize('change,reason',[
 ('stale','STALE_CURRENT_CHECK'),('future','FUTURE_CHECK_TIME'),('schedule','SCHEDULE_CHANGED'),
 ('public','RESULTS_ALREADY_PUBLIC'),('unresolved','RESULTS_ALREADY_PUBLIC'),('roles','REQUIRED_COVERAGE'),
 ('coverage','PUBLICATION_DATE_COVERAGE'),('incomplete','PAGE_COVERAGE'),('contradiction','CONTRADICTORY'),
 ('timezone','CHECK_TIMEZONE'),('call','RESULTS_PUBLICATION'),('pagination','PUBLICATION_COVERAGE')])
def test_missing_contradictory_stale_or_unresolved_checks_block(change,reason):
    c,e,clock,d=fixture()
    if change=='stale':d['pages'][0]['checked_at']=(clock-timedelta(seconds=601)).isoformat()
    elif change=='future':d['pages'][1]['checked_at']=(clock+timedelta(seconds=1)).isoformat()
    elif change=='schedule':d['schedule']['release_date']='2026-12-02'
    elif change=='public':d['publication']['status']='already_public'
    elif change=='unresolved':d['publication']['status']='unknown'
    elif change=='roles':d['pages'].pop()
    elif change=='coverage':d['publication']['coverage_from']='2026-10-31'
    elif change=='incomplete':d['pages'][1]['complete']=False
    elif change=='contradiction':d['contradictions']=['Schedule differs']
    elif change=='timezone':d['timezone']='America/Los_Angeles' # source timestamps explicitly UTC
    elif change=='call':d['schedule']['event_kind']='earnings_call'
    elif change=='pagination':d['publication']['pagination_complete']=False
    assert any(reason in g for g in checks.assess(d,c,e,clock)['gaps'])

def test_ttl_boundary_and_tamper():
    c,e,clock,d=fixture()
    for p in d['pages']:p['checked_at']=(clock-timedelta(minutes=10)).isoformat()
    r=sealed(d,c,e,clock);assert checks.validate_record(r,c,e,clock)['status']=='usable'
    with pytest.raises(Blocked):checks.validate_record(r,c,e,clock+timedelta(microseconds=1))
    r['data']['observer']='edited'
    with pytest.raises(Blocked,match='edited'):checks.validate_record(r,c,e,clock)

def test_independent_sec_failure_or_suspect_blocks_even_with_complete_owner_check(monkeypatch):
    c,e,clock,d=fixture();r=sealed(d,c,e,clock);monkeypatch.setattr(live,'verify_durable',lambda c,e:e)
    for sec in [dict(success=False),dict(success=True,status='possible_results',checked_at=clock.isoformat()),dict(success=True,status='clear',checked_at=(clock-timedelta(seconds=601)).isoformat())]:
        with pytest.raises(Blocked):checks.owner_pair(r,c,c['quarter_targets'][-1],e,clock=clock,sec_check=lambda *a:sec)

def test_intake_preserves_input_and_generates_actual_receipt_time(tmp_path,monkeypatch):
    c,e,clock,d=fixture();monkeypatch.setattr(checks,'now',lambda:clock)
    p=tmp_path/'supplied.json';body=json.dumps(d).encode();p.write_bytes(body)
    r=checks.intake(p,directory=tmp_path/'records')
    assert r['ingested_at']==clock.isoformat() and (tmp_path/'records/inputs'/(r['input_sha256']+'.json')).read_bytes()==body
    d['ingested_at']='2020-01-01';p.write_text(json.dumps(d));blocked=checks.intake(p,directory=tmp_path/'records')
    assert blocked['assessment']['status']=='blocked'
    assert checks.latest(tmp_path/'records','OKTA')['id']==blocked['id']

@pytest.fixture
def owner_db(db_conn,monkeypatch):
    c=deepcopy(companies()['OKTA']);store.register(db_conn,c)
    clock=db_conn.execute('SELECT clock_timestamp()').fetchone()[0].astimezone(timezone.utc)
    target={'start':str(clock.date()-timedelta(days=104)),'end':str(clock.date()-timedelta(days=15)),'label':'Q3 FY2027'};c['quarter_targets']=[target]
    g=replace(guidance(issued=str(clock.date()-timedelta(days=90)),low='300',high='350'),company='OKTA',start=date.fromisoformat(target['start']),end=date.fromisoformat(target['end']),metric='quarterly_consolidated_revenue')
    store.save_guidance(db_conn,g);db_conn.execute('SET LOCAL ROLE service_role');ids=[]
    for row in rows('OKTA'):
        ids.append(row['id']);store.insert(db_conn,'earnings_historical_observations',dict(id=row['id'],company_id=store.company_id('OKTA'),period_start=row['period_start'],period_end=row['period_end'],guidance_id=g.id,actual_id=str(uuid4()),status='eligible',outcome=row['outcome'],public_available_at=baseline.aware(row['public_available_at']),payload=Jsonb(row)))
    clock=db_conn.execute('SELECT clock_timestamp()').fetchone()[0].astimezone(timezone.utc)
    b=baseline.probabilities('OKTA',[v for v in history.stored(db_conn) if v['id'] in ids],clock)
    e={'fiscal_period':target,'id':str(uuid4()),'company':'OKTA','event_kind':'results_release','verification_status':'user_verified','verification_method':'owner_pdf_document_review_v1',
       'source_url':'https://investor.okta.com/synthetic-announcement','source_sha256':'a'*64,'owner_intake_id':str(uuid4()),'supplied_by':'Synthetic owner',
       'owner_retrieved_at':(clock-timedelta(days=2)).isoformat(),'checked_at':(clock-timedelta(days=2)).isoformat(),
       'release_date':str(clock.date()+timedelta(days=3)),'timezone':'America/New_York','time_precision':'market_session','release_time':'after_market_close'}
    d=data_for(c,e,clock);record=sealed(d,c,e,clock)
    monkeypatch.setattr(live,'verify_durable',lambda c,e:e)
    sec={'success':True,'status':'clear','checked_at':clock.isoformat(),'possible_results_filings':[],'manifest':{'url':'https://data.sec.gov/submissions/CIK'+c['cik']+'.json'}}
    e2,pub=checks.owner_pair(record,c,target,e,clock=clock,sec_check=lambda *a:sec)
    return db_conn,c,target,g,b,e2,pub

def test_db_accepts_old_durable_pdf_with_current_owner_and_independent_sec_checks(owner_db):
    conn,c,target,g,b,e,pub=owner_db
    assert live.insert_prediction(conn,c,target,g,b,e,pub)
    assert live.insert_prediction(conn,c,target,g,smoothed_baseline.from_empirical(b),e,pub)
    assert e['owner_retrieved_at']==e['checked_at'] and e['prelock_schedule_check']['checked_at']!=e['checked_at']

@pytest.mark.parametrize('fault',['schedule','public','coverage','contradiction','stale_page','sec_suspect','sec_stale','roles'])
def test_db_rejects_forged_or_incomplete_owner_checks(owner_db,fault):
    conn,c,target,g,b,e,pub=owner_db;e=deepcopy(e);pub=deepcopy(pub)
    if fault=='schedule':e['prelock_schedule_check']['observed_schedule']['release_date']='2099-01-01'
    elif fault=='sec_suspect':pub['sec']['possible_results_filings']=[{'accession':'suspect'}]
    elif fault=='sec_stale':pub['sec']['checked_at']='2020-01-01T00:00:00Z'
    else:
        data=e['prelock_schedule_check']['owner_record']['data']
        if fault=='public':data['publication']['status']='already_public'
        elif fault=='coverage':data['publication']['coverage_from']=target['end']
        elif fault=='contradiction':data['contradictions']=['different schedule']
        elif fault=='stale_page':data['pages'][0]['checked_at']='2020-01-01T00:00:00Z'
        elif fault=='roles':data['pages']=data['pages'][:2]
        pub['official_ir']['owner_record']=deepcopy(e['prelock_schedule_check']['owner_record'])
    with pytest.raises(psycopg.Error):
        with conn.transaction():live.insert_prediction(conn,c,target,g,b,e,pub)

def test_automated_inventory_new_schedule_notice_blocks(monkeypatch,tmp_path):
    c=companies()['OKTA'];target=c['quarter_targets'][-1];e=live.announcement(c)
    monkeypatch.setattr(live,'sec_publication_check',lambda *a:dict(success=True,status='clear'))
    monkeypatch.setattr(live,'CACHE',tmp_path)
    class Response:
        status_code=200
        content=b'<h2>November 16, 2026</h2><a href="/new-schedule">Okta to Announce Third Quarter Fiscal 2027 Financial Results</a><a>Reports Second Quarter Financial Results</a>'
    monkeypatch.setattr(live.requests,'get',lambda *a,**k:Response())
    r=live.publication_check(c,target)
    assert r['status']=='schedule_update_or_unresolved_ir_notice'
    assert r['official_ir']['possible_schedule_notices'][0]['url']!=e['source_url']


def test_automated_refresh_does_not_change_durable_timestamp(monkeypatch):
    c,e,clock,d=fixture();original=deepcopy(e)
    monkeypatch.setattr(live,'verify_durable',lambda c,e:e)
    monkeypatch.setattr(live,'check_source',lambda *a,**k:dict(status='confirmed',sha256=e['source_sha256'],checked_at=clock.isoformat()))
    updated=live.refresh_announcement(c,e)
    assert updated['checked_at']==original['checked_at'] and e==original
    assert updated['prelock_schedule_check']['checked_at']==clock.isoformat()


def test_invalid_owner_intake_never_matures_into_valid_evidence():
    c,e,clock,d=fixture()
    for p in d['pages']:p['checked_at']=(clock+timedelta(seconds=1)).isoformat()
    r=sealed(d,c,e,clock)
    with pytest.raises(Blocked,match='Invalid original intake'):
        checks.validate_record(r,c,e,clock+timedelta(seconds=2))
