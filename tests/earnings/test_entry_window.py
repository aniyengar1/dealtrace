"""Entry-only change. All timestamps/evidence in simulations are test fixtures."""
from copy import deepcopy
from dataclasses import replace
from contextlib import nullcontext
from datetime import datetime,date,timedelta,timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
import pytest
import psycopg
from earnings import live,predict,history,store,baseline,smoothed_baseline,current_checks
from earnings.lock_window import opening,VERSION
from earnings.registry import companies,load_guidance
from earnings.models import Actual,DateInterval
from test_current_checks import owner_db,data_for,sealed

METHODS=(baseline.METHOD,smoothed_baseline.METHOD)

@pytest.mark.parametrize('release,stamp',[('2026-12-01','2026-11-14T05:00:00+00:00'),('2026-12-02','2026-11-15T05:00:00+00:00'),('2026-12-03','2026-11-16T05:00:00+00:00')])
def test_each_new_opening_and_unchanged_deadline(db_conn,release,stamp):
    e=dict(event_kind='results_release',verification_status='independently_verified',timezone='America/New_York',release_date=release,time_precision='market_session')
    due=live.deadline(e);start=datetime.fromisoformat(stamp)
    assert opening(due,e['timezone'])==start
    assert db_conn.execute('SELECT earnings_lock_opening(%s,%s)',(due,e['timezone'])).fetchone()[0]==start
    for clock,expected in [(start-timedelta(microseconds=1),False),(start,True),(start+timedelta(microseconds=1),True),(due-timedelta(microseconds=1),True),(due,False)]:
        assert (start<=clock<due)==expected
        result=db_conn.execute('SELECT %s >= earnings_lock_opening(%s,%s) AND %s < %s',(clock,due,e['timezone'],clock,due)).fetchone()[0]
        assert result==expected

@pytest.mark.parametrize('release',['2026-03-15','2026-11-08'])
def test_calendar_days_respect_release_timezone_across_dst(db_conn,release):
    due=datetime.combine(date.fromisoformat(release),datetime.min.time(),ZoneInfo('America/New_York'))
    actual=opening(due,'America/New_York')
    assert actual.astimezone(ZoneInfo('America/New_York')).date()==due.date()-timedelta(days=17)
    assert actual.astimezone(ZoneInfo('America/New_York')).hour==0
    assert db_conn.execute('SELECT earnings_lock_opening(%s,%s)',(due,'America/New_York')).fetchone()[0]==actual

class Cursor:
    def __init__(self,value):self.value=value
    def fetchone(self):return self.value
class NoWriteConnection:
    def __init__(self,clock):self.clock=clock
    def execute(self,sql,params=None):
        if sql=='SET LOCAL ROLE service_role':return Cursor(None)
        if sql=='SELECT clock_timestamp()':return Cursor((self.clock,))
        if sql.startswith('SELECT id,made_at FROM earnings_live_predictions'):return Cursor(None)
        raise AssertionError('Simulated test forbids SQL writes')
    def transaction(self):return nullcontext()

def simulate(monkeypatch,ticker,clock,*,guides=None,mode='clean'):
    c=companies()[ticker];target=c['quarter_targets'][-1]
    # Synthetic release date for the uniformity test, never written as evidence.
    e=dict(company=ticker,event_kind='results_release',verification_status='independently_verified',timezone='America/New_York',release_date='2026-12-03',time_precision='market_session')
    obs=deepcopy(history.load_all())
    for r in obs:r['recorded_at']='2026-11-13T00:00:00+00:00'
    monkeypatch.setattr(history,'stored',lambda conn:obs)
    monkeypatch.setattr(history,'ingest',lambda conn:{'inserted':0})
    fake_actual=Actual(ticker,'Revenues',date(2026,1,1),date(2026,7,31),Decimal(100),'USD','US_GAAP_consolidated_reported','synthetic-not-live',date(2026,8,1),'10-Q',2027,'Q2','https://data.sec.gov/synthetic-fixture')
    monkeypatch.setattr(store,'records',lambda conn,t:([fake_actual],guides or load_guidance(t)))
    captures=[]
    def capture(conn,c,target,g,b,e,check):
        captures.append({'guide':g.id,'baseline':b,'evidence':deepcopy(e)});return {'dry_run':True}
    monkeypatch.setattr(predict,'insert_prediction',capture)
    result=predict.run(NoWriteConnection(clock),{ticker:c},methods=METHODS,announcement_loader=lambda c:e,refresh=lambda c,e:e,publication=lambda c,t:{'status':'not_observed' if mode=='clean' else 'already_public_synthetic'})
    return result,captures

@pytest.mark.parametrize('ticker',list(companies()))
def test_both_methods_uniform_boundary_and_original_horizon(monkeypatch,ticker):
    start=datetime.fromisoformat('2026-11-16T05:00:00+00:00')
    before,items=simulate(monkeypatch,ticker,start-timedelta(microseconds=1))
    assert not items and before['skipped'][0]['code']=='OUTSIDE_LOCK_WINDOW'
    at,items=simulate(monkeypatch,ticker,start)
    assert len(items)==2 and not at['skipped']
    a,b=items;assert a['guide']==b['guide'] and a['baseline']['historical_ids']==b['baseline']['historical_ids']
    assert a['baseline']['as_of']==b['baseline']['as_of']
    assert a['baseline']['method_version']==METHODS[0] and b['baseline']['method_version']==METHODS[1]
    assert b['baseline']==smoothed_baseline.from_empirical(a['baseline'])
    assert baseline.guidance_cutoff('2026-12-03')==date(2026,11,18) # frozen historical rule, not D-18
    due=datetime.fromisoformat('2026-12-03T05:00:00+00:00')
    after,items=simulate(monkeypatch,ticker,due)
    assert not items and after['skipped'][0]['code']=='LOCK_DEADLINE_PASSED'


def test_early_entry_never_selects_future_day_precision_guidance(monkeypatch):
    clock=datetime.fromisoformat('2026-11-16T05:00:00+00:00');guides=load_guidance('OKTA')
    base=next(g for g in guides if g.metric=='quarterly_consolidated_revenue')
    for issued,filed in [('2026-11-17','2026-11-17'),('2026-11-16','2026-11-16')]:
        future=replace(base,issued=DateInterval.read(issued),filed=date.fromisoformat(filed),low=base.low+1,high=base.high+1)
        r,items=simulate(monkeypatch,'OKTA',clock,guides=guides+[future])
        assert len(items)==2 and all(i['guide']!=future.id for i in items)
    published=replace(base,issued=DateInterval.read('2026-11-15'),filed=date(2026,11,15),low=base.low+1,high=base.high+1)
    r,items=simulate(monkeypatch,'OKTA',clock,guides=guides+[published]);assert all(i['guide']==published.id for i in items)


def change_release(owner_db,days):
    conn,c,target,g,b,e,pub=owner_db;clock=conn.execute('SELECT clock_timestamp()').fetchone()[0].astimezone(timezone.utc)
    e={k:v for k,v in e.items() if k!='prelock_schedule_check'};e['release_date']=str(clock.date()+timedelta(days=days))
    d=data_for(c,e,clock);record=sealed(d,c,e,clock)
    updated,check=current_checks.owner_pair(record,c,target,e,clock=clock,sec_check=lambda *a:pub['sec'])
    return conn,c,target,g,b,updated,check,clock


def test_sql_both_methods_admit_extra_window_with_real_db_time(owner_db):
    conn,c,t,g,b,e,pub,clock=change_release(owner_db,16)
    assert live.deadline(e)-clock>timedelta(days=14)
    for method in [b,smoothed_baseline.from_empirical(b)]:
        saved=live.insert_prediction(conn,c,t,g,method,e,pub);assert saved
        snap=conn.execute('SELECT snapshot FROM earnings_live_predictions WHERE id=%s',(saved['id'],)).fetchone()[0]
        assert snap['live_entry_policy']['version']==VERSION and snap['live_entry_policy']['calendar_days']==17

@pytest.mark.parametrize('days',[18,-1])
def test_sql_rejects_outside_new_window_and_passed_deadline(owner_db,days):
    conn,c,t,g,b,e,pub,clock=change_release(owner_db,days)
    for method in [b,smoothed_baseline.from_empirical(b)]:
        with pytest.raises(psycopg.Error,match='17-calendar-day'):
            with conn.transaction():live.insert_prediction(conn,c,t,g,method,e,pub)


def test_sql_rejects_not_yet_public_guidance_during_early_entry(owner_db):
    conn,c,t,g,b,e,pub,clock=change_release(owner_db,16)
    future=replace(g,issued=DateInterval.read(str(clock.date()+timedelta(days=1))),filed=clock.date()+timedelta(days=1))
    store.save_guidance(conn,future)
    for method in [b,smoothed_baseline.from_empirical(b)]:
        with pytest.raises(psycopg.Error,match='actual public cutoff'):
            with conn.transaction():live.insert_prediction(conn,c,t,future,method,e,pub)
