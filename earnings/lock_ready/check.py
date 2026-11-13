"""External read-only harness. Production lock modules are never edited.

python earnings/lock_ready/check.py --code-root <tag archive or current root>
Adapters suppress history ingestion and ledger insertion. PostgreSQL READ ONLY
is an independent guard even if a future code path attempts a write.
"""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,timezone
from contextlib import nullcontext
from dataclasses import replace

p=argparse.ArgumentParser();p.add_argument('--code-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--regression',action='store_true');args=p.parse_args()
sys.path.insert(0,str(args.code_root.resolve()))
# Load secrets only through dotenv, never display or serialize environment values.
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2]/'.env')
from earnings import predict,history,store
from earnings.registry import companies,load_guidance
from earnings.live import announcement
from earnings.actuals import Blocked
from earnings.models import dumps,Actual,DateInterval


def protected_run(conn,registry,**kwargs):
    original_ingest=history.ingest;original_insert=predict.insert_prediction
    captures=[]
    try:
        history.ingest=lambda conn:{'inserted':0,'dry_run_history_ingestion_suppressed':True}
        def capture(conn,c,target,g,b,e,check):
            captures.append({'company':c['ticker'],'target':target,'guidance_id':g.id,'historical_input_ids':b['historical_ids'],'probabilities':b['probabilities'],'method_version':b['method_version']})
            return {'dry_run':True,'database_insert_executed':False}
        predict.insert_prediction=capture
        result=predict.run(conn,registry,**kwargs)
        result['eligible_candidates']=captures;result['locked']=[]
        return result
    finally:history.ingest=original_ingest;predict.insert_prediction=original_insert


if not args.regression:
    conn=store.connect()
    try:
        conn.execute('BEGIN READ ONLY')
        readonly=conn.execute('SHOW transaction_read_only').fetchone()[0]
        before=conn.execute('SELECT count(*) FROM earnings_live_predictions').fetchone()[0]
        schema=[r[0] for r in conn.execute('SELECT filename FROM schema_migrations ORDER BY filename')]
        required={p.name for p in (args.code_root/'db/migrations').glob('01*.sql')}
        if not required.issubset(set(schema)):raise RuntimeError('Lock-ready schema migrations missing')
        stored={r['id'] for r in history.stored(conn)};missing=sorted(r['id'] for r in history.load_all() if r['id'] not in stored)
        result=protected_run(conn,companies());after=conn.execute('SELECT count(*) FROM earnings_live_predictions').fetchone()[0]
        result.update(dry_run=True,ledger_writes_possible=False,transaction_read_only=readonly,
            ledger_count_before=before,ledger_count_after=after,unimported_history_ids=missing,
            schema_migrations=schema,schema_compatible=True)
    finally:conn.rollback();conn.close()
else:
    from decimal import Decimal
    from earnings.baseline import day_available
    reg=companies();observations=history.load_all()
    for row in observations:row['recorded_at']='2026-11-13T00:00:00+00:00' # explicitly synthetic test fixture, not a DB entry
    class Cursor:
        def __init__(self,value):self.value=value
        def fetchone(self):return self.value
    class Connection:
        def __init__(self,clock):self.clock=clock
        def execute(self,query,params=None):
            if query=='SET LOCAL ROLE service_role':return Cursor(None)
            if query=='SELECT clock_timestamp()':return Cursor((self.clock,))
            if query.startswith('SELECT id,made_at FROM earnings_live_predictions'):return Cursor(None)
            raise AssertionError('Synthetic harness forbids other SQL')
        def transaction(self):return nullcontext()
    original_stored=history.stored;original_records=store.records
    try:
        results=[]
        for case,stamp in [('outside','2026-11-13T12:00:00+00:00'),('inside','2026-11-20T12:00:00+00:00'),('deadline','2026-12-03T05:00:00+00:00'),('withdrawn','2026-11-20T12:00:00+00:00'),('stale_actual','2026-11-20T12:00:00+00:00'),('already_public','2026-11-20T12:00:00+00:00'),('missing_history','2026-11-20T12:00:00+00:00')]:
            clock=datetime.fromisoformat(stamp)
            history.stored=lambda conn:[] if case=='missing_history' else observations
            def records(conn,ticker):
                guides=load_guidance(ticker)
                if case=='withdrawn':
                    base=next(g for g in guides if g.metric=='quarterly_consolidated_revenue')
                    guides.append(replace(base,status='withdrawn',low=None,high=None,original_verified=False,issued=DateInterval.read('2026-11-18'),filed=datetime(2026,11,18).date()))
                end='2026-01-31' if case=='stale_actual' else '2026-07-31'
                a=Actual(ticker,'Revenues',datetime(2026,1,1).date(),datetime.fromisoformat(end).date(),Decimal(100),'USD','US_GAAP_consolidated_reported','synthetic-not-live',datetime(2026,8,1).date(),'10-Q',2027,'Q2','https://data.sec.gov/synthetic-fixture')
                return [a],guides
            store.records=records
            r=protected_run(Connection(clock),reg,announcement_loader=announcement,refresh=lambda c,e:e,
                publication=lambda c,t:{'status':'already_public_synthetic' if case=='already_public' else 'not_observed'})
            results.append({'case':case,'synthetic_fixed_time':stamp,'eligible_candidates':r['eligible_candidates'],'rejections':r['skipped']})
        result={'kind':'synthetic_fixed_input_regression_NOT_live','cases':results,'database_access':False,'ledger_writes_possible':False}
    finally:history.stored=original_stored;store.records=original_records
args.output.parent.mkdir(parents=True,exist_ok=True)
with args.output.open('x') as stream:stream.write(dumps(result)+'\n')
print(dumps({'output':str(args.output),'kind':result.get('kind','actual-clock READ ONLY dry run'),'ledger_writes_possible':False}))
