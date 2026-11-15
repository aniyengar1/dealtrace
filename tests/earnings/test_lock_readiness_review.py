"""Review-only eligibility-boundary rehearsal; simulated time lives ONLY in tests.

Run directly for a READ ONLY DB snapshot, not a live lock:
  .venv/bin/python tests/earnings/test_lock_readiness_review.py --output <new.json>
No provider, SEC or IR requests. Production INSERT is replaced by an in-memory
capture; PostgreSQL READ ONLY is a separate guard. SQL timestamp guards are not
executed with simulated time. Their age expressions are tested independently.
"""
import argparse,json,sys
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from earnings import predict,history,store,live
from earnings.registry import companies
from earnings.models import plain,dumps
from earnings.actuals import Blocked

OPEN=datetime.fromisoformat('2026-11-17T05:00:00+00:00')
DUE=datetime.fromisoformat('2026-12-01T05:00:00+00:00')
METHODS=('quarter-frequency-v1','quarter-frequency-laplace-v1')

def ttl_passes(stamp,clock,seconds):
    """Exact inclusive current-check age expression in migration0106; test helper only."""
    return stamp is not None and clock-timedelta(seconds=seconds)<=stamp<=clock

class ClockRow:
    def __init__(self,clock):self.clock=clock
    def fetchone(self):return (self.clock,)
class ControlledClockConnection:
    def __init__(self,real,clock):self.real=real;self.clock=clock
    def execute(self,query,params=None):
        if query=='SELECT clock_timestamp()':return ClockRow(self.clock)
        if str(query).lstrip().upper().startswith(('INSERT','UPDATE','DELETE','TRUNCATE','ALTER','CREATE','DROP')):
            raise AssertionError('Rehearsal forbids mutating SQL')
        return self.real.execute(query,params)
    def transaction(self):return self.real.transaction()

def scenario(conn,company,clock,mode):
    captures=[];evidence=live.announcement(company)
    def refresh(c,e):
        if mode=='announcement_403':raise Blocked('ANNOUNCEMENT_ACCESS_GAP','Synthetic403: NOT an actual source observation')
        if mode=='announcement_hash_change':raise Blocked('ANNOUNCEMENT_SOURCE_CHANGED','Synthetic changed raw HTML hash; NOT an actual source observation')
        if mode=='stored_announcement_only':return e
        # A hypothetical new source check, confined to test data in memory.
        return {**e,'prelock_schedule_check':{'policy_version':'current-state-checks-v2','checked_at':(clock-timedelta(seconds=1)).isoformat(),'method':'automated_http','synthetic_test_fixture':True}}
    def publication(c,target):
        result={'checked_at':(clock-timedelta(seconds=1)).isoformat(),'status':'not_observed',
            'target_start':target['start'],'target_end':target['end'],
            'policy_version':'current-state-checks-v2','sec':{'success':True,'status':'clear','checked_at':(clock-timedelta(seconds=1)).isoformat(),'synthetic_test_fixture':True},'official_ir':{'success':True,'checked_at':(clock-timedelta(seconds=1)).isoformat(),'synthetic_test_fixture':True},
            'synthetic_test_fixture':True}
        if mode=='publication_403':result.update(status='unverified',official_ir={'success':False,'http_status':403,'synthetic_test_fixture':True})
        if mode=='publication_empty':result.update(status='unverified',official_ir={'success':False,'gap':'Synthetic empty/loading inventory'})
        if mode=='already_public':result['status']='already_public_or_unresolved_ir_results'
        if mode=='possible_sec_result':result['status']='already_public_or_unresolved_sec_results'
        if mode=='stale_publication':result['checked_at']=(clock-timedelta(seconds=601)).isoformat()
        return result
    def capture(c,registry,target,g,b,e,check):
        # Emulate only TTL preconditions; do NOT run DB INSERT or fake DB time.
        stamp=e.get('prelock_schedule_check',{}).get('checked_at')
        if not ttl_passes(datetime.fromisoformat(stamp) if stamp else None,clock,600):
            raise Blocked('REHEARSAL_SQL_ANNOUNCEMENT_STALE','Current0106 requires a separate fresh schedule check; durable retrieval is insufficient')
        if not ttl_passes(datetime.fromisoformat(check['checked_at']),clock,600):
            raise Blocked('REHEARSAL_SQL_PUBLICATION_STALE','Current0106 freshness expression would reject this publication check')
        captures.append({'company':registry['ticker'],'target':target,'guidance_id':g.id,
            'guidance':plain(g),'baseline':plain(b),'announcement_evidence_id':e['id'],
            'durable_checked_at_preserved':e.get('checked_at')==evidence.get('checked_at'),'hypothetical_source_checks':True,'method_version':b['method_version']})
        return {'dry_run':True,'database_insert_executed':False}
    checks=None
    if mode.startswith('owner_'):
        from test_current_checks import data_for,sealed
        from earnings import current_checks
        def checks(c,target,e):
            d=data_for(c,e,clock)
            if mode=='owner_incomplete':d['pages'].pop()
            if mode=='owner_schedule_changed':d['schedule']['release_date']='2026-12-02'
            if mode=='owner_already_public':d['publication']['status']='already_public'
            if mode=='owner_stale':d['pages'][0]['checked_at']=(clock-timedelta(seconds=601)).isoformat()
            record=sealed(d,c,e,clock)
            sec={'success':True,'status':'clear','checked_at':clock.isoformat(),'possible_results_filings':[],'synthetic_test_fixture':True}
            with patch.object(live,'verify_durable',lambda c,e:e):
                return current_checks.owner_pair(record,c,target,e,clock=clock,sec_check=lambda *a:sec)
    with patch.object(history,'ingest',lambda c:{'inserted':0,'suppressed_for_read_only_rehearsal':True}),patch.object(predict,'insert_prediction',capture),patch.object(live.requests,'get',side_effect=AssertionError('No HTTP allowed')),patch.object(live,'fetch',side_effect=AssertionError('No SEC request allowed')):
        r=predict.run(ControlledClockConnection(conn,clock),{company['ticker']:company},methods=METHODS,checks=checks,refresh=refresh,publication=publication)
    r['clock_source']='TEST_ONLY_CONTROLLED_CLOCK_NOT_POSTGRES_CREATION_TIME'
    r['locked']=[];r['conditional_candidates_NOT_live']=captures
    return {'test_clock':clock.isoformat(),'mode':mode,'result':r,'database_insert_guards_executed':False}

def rehearse(conn):
    conn.execute('BEGIN READ ONLY');real_start=conn.execute('SELECT clock_timestamp()').fetchone()[0]
    before=conn.execute('SELECT count(*) FROM earnings_live_predictions').fetchone()[0]
    company=deepcopy(companies()['OKTA'])
    cases=[]
    for clock,mode in [(OPEN-timedelta(microseconds=1),'hypothetical_clean_checks'),(OPEN,'hypothetical_clean_checks'),
        (OPEN+timedelta(microseconds=1),'hypothetical_clean_checks'),(DUE,'hypothetical_clean_checks'),
        (OPEN,'stored_announcement_only'),(OPEN,'announcement_403'),(OPEN,'announcement_hash_change'),
        (OPEN,'publication_403'),(OPEN,'publication_empty'),(OPEN,'already_public'),(OPEN,'possible_sec_result'),(OPEN,'stale_publication'),(OPEN,'owner_complete'),(OPEN,'owner_incomplete'),(OPEN,'owner_schedule_changed'),(OPEN,'owner_already_public'),(OPEN,'owner_stale')]:
        cases.append(scenario(conn,company,clock,mode))
    assert cases[0]['result']['skipped'][0]['code']=='OUTSIDE_14_DAY_WINDOW'
    for i in (1,2):
        a,b=cases[i]['result']['conditional_candidates_NOT_live'];assert (a['method_version'],b['method_version'])==METHODS
        assert a['guidance_id']==b['guidance_id'] and a['baseline']['historical_ids']==b['baseline']['historical_ids']
        assert a['baseline']['as_of']==b['baseline']['as_of']
    assert cases[3]['result']['skipped'][0]['code']=='LOCK_DEADLINE_PASSED'
    for c in cases[4:]:
        if c['mode']=='owner_complete':
            a,b=c['result']['conditional_candidates_NOT_live'];assert a['guidance_id']==b['guidance_id'] and a['baseline']['historical_ids']==b['baseline']['historical_ids']
            assert a['durable_checked_at_preserved'] and b['durable_checked_at_preserved']
        else:assert not c['result']['conditional_candidates_NOT_live'] and c['result']['skipped']
    after=conn.execute('SELECT count(*) FROM earnings_live_predictions').fetchone()[0]
    assert before==after==0
    actuals,guides=store.records(conn,'OKTA');obs=history.stored(conn)
    target=company['quarter_targets'][-1]
    result={'kind':'TEST_ONLY_BOUNDARY_REHEARSAL_NOT_LIVE_NOT_FUTURE_SOURCE_VERIFICATION',
        'actual_execution_started_at':real_start.isoformat(),'actual_execution_finished_at':conn.execute('SELECT clock_timestamp()').fetchone()[0].isoformat(),
        'transaction_read_only':conn.execute('SHOW transaction_read_only').fetchone()[0],
        'ledger_count_before':before,'ledger_count_after':after,'provider_or_HTTP_calls':0,
        'production_clock_or_code_changed':False,'SQL_insert_guards_executed_with_test_time':False,
        'source_snapshot_limit':'Only currently stored inputs, not unknown future updates. Successful source checks are hypothetical fixtures; not real verification.',
        'opening':OPEN.isoformat(),'strict_deadline':DUE.isoformat(),'company':'OKTA',
        'latest_actual_period_end':str(max(a.end for a in actuals)),
        'freshness_actual_ids':sorted(a.id for a in actuals if a.end==max(v.end for v in actuals)),
        'stored_history_rows':len(obs),'cases':cases}
    return result

def test_opening_and_closing_are_exact():
    e={'verification_status':'independently_verified','event_kind':'results_release','timezone':'America/New_York','release_date':'2026-12-01','time_precision':'market_session'}
    assert live.deadline(e)==DUE and DUE-timedelta(days=14)==OPEN
    assert DUE-(OPEN-timedelta(microseconds=1))>timedelta(days=14)
    assert DUE-OPEN==timedelta(days=14)

def test_ttl_exact_limits_and_future_rejection():
    assert ttl_passes(OPEN-timedelta(minutes=10),OPEN,600)
    assert not ttl_passes(OPEN-timedelta(minutes=10,microseconds=1),OPEN,600)
    assert not ttl_passes(OPEN+timedelta(microseconds=1),OPEN,600)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior output; choose a new filename')
    with store.connect() as conn:
        try:r=rehearse(conn)
        finally:conn.rollback()
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(dumps(r)+'\n')
    print(dumps({'output':str(a.output),'case_count':len(r['cases']),'ledger_before':r['ledger_count_before'],'ledger_after':r['ledger_count_after'],'test_only':True}))
