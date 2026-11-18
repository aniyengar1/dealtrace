"""Historical scoring rehearsal in TEMP scratch tables/views, never live ledger DML.

A source SQLite archive was exported separately using READ ONLY. Historical
as-of timestamps below are retrospective inputs, NOT prediction creation times.
All scratch creation/scoring clocks remain actual PostgreSQL clocks. No new locks.
"""
import argparse,json,re,tempfile
from pathlib import Path
from datetime import datetime,timezone,date,time,timedelta
from uuid import UUID,uuid5
from psycopg.types.json import Jsonb
from earnings import store,score_live,baseline,smoothed_baseline
from earnings.publication.export import read_copy
from earnings.models import dumps,plain
from earnings.actuals import Blocked

NS=UUID('f6f8bb27-359f-44d0-9a36-cb57689f2724')

def cases(data):
    rows=[{**r['payload'],'recorded_at':r['recorded_at']} for r in data['historical_observations']];chosen=[]
    # Coverage-oriented selection using known labels, not a forecast evaluation.
    for outcome in ('below','within','above'):
        for row in sorted(rows,key=lambda r:(r['period_end'],r['company'],r['id']),reverse=True):
            if row['status']!='eligible' or row['outcome']!=outcome:continue
            s=row['source_record'];day=date.fromisoformat(s['guidance_anchor_publication_date'])
            historical_asof=datetime.combine(day-timedelta(days=14),time.min,baseline.ZoneInfo(baseline.ZONE))
            try:b=baseline.probabilities(row['company'],rows,historical_asof,retrospective=True)
            except Blocked:continue
            assert row['id'] not in b['historical_ids']
            chosen.append((row,b,historical_asof));break
    if len(chosen)!=3:raise ValueError('Need three eligible historical outcomes for coverage')
    return chosen

def review_for(row):
    s=row['source_record'];r=s['result'];basis=s['outcome_basis_review']
    return {'actual':s['actual'],'actual_parents':s.get('actual_parents',[]),
        'first_result_publication_lower_bound':datetime.combine(date.fromisoformat(r['issued_date']),time.min,baseline.ZoneInfo(baseline.ZONE)).isoformat(),
        'evidence_available_at':row['public_available_at'],
        'result_source':{'url':r['source_url'],'accession':r['accession'],'filed_date':r['filed'],'issued_date':r['issued_date'],'issuance_date_quote':r['date_quote'],'quote':r['reported_revenue_quote'],'exhibit':r['exhibit_identifier']},
        'outcome_basis_review':{'actual_id':row['actual_id'],'guidance_id':row['guidance_id'],'blocked':False,'available_on':basis['reviewed_at'][:10],'sources':basis['sources'],'verifier':basis['verifier'],'reviewed_at':basis['reviewed_at'],'reason':basis['reason']},
        'rehearsal_provenance':'Existing agent/source-curated history, not new owner review; retrospective scoring-mechanics fixture, not a live forecast.'}

def setup(conn):
    conn.execute('CREATE TEMP TABLE scratch_scoring_inputs(id UUID PRIMARY KEY,payload JSONB NOT NULL,scratch_created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),fixture_kind TEXT NOT NULL DEFAULT \'retrospective-not-live\')')
    conn.execute('''CREATE TEMP VIEW earnings_live_predictions AS SELECT id,(payload->>'historical_asof')::timestamptz made_at,
        (payload->>'guidance_id')::uuid guidance_id,payload->'snapshot' snapshot,
        (payload->>'p_below')::numeric p_below,(payload->>'p_within')::numeric p_within,(payload->>'p_above')::numeric p_above FROM scratch_scoring_inputs''')
    for table in ('earnings_actuals','earnings_actual_edges','earnings_live_results'):
        conn.execute(f'CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)')
    sql=Path('db/migrations/0103_crosscheck_live_ledger.sql').read_text();body=re.search(r'CREATE FUNCTION earnings_result_guard\(\).*?AS \$\$(.*?)\$\$;',sql,re.S).group(1)
    # Same frozen body, isolated namespace. No public trigger/function is changed.
    conn.execute('CREATE FUNCTION pg_temp.scratch_result_guard() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_temp,pg_catalog AS $$'+body+'$$')
    conn.execute('CREATE TRIGGER scratch_result_validate BEFORE INSERT ON pg_temp.earnings_live_results FOR EACH ROW EXECUTE FUNCTION pg_temp.scratch_result_guard()')
    for name in ('scratch_scoring_inputs','earnings_live_predictions','earnings_actuals','earnings_actual_edges','earnings_live_results'):
        conn.execute(f'GRANT ALL ON pg_temp.{name} TO service_role')
    conn.execute('SET LOCAL search_path=pg_temp,pg_catalog')
    for table in ('earnings_live_predictions','earnings_live_results','earnings_actuals','earnings_actual_edges'):
        assert conn.execute('SELECT to_regclass(%s)=to_regclass(%s)',(table,'pg_temp.'+table)).fetchone()[0]

class ScratchOnly:
    """Reject any SQL outside the frozen scorer's small scratch-only query set."""
    def __init__(self,conn):self.conn=conn
    def execute(self,query,params=None):
        q=str(query)
        allowed=('SET LOCAL ROLE service_role','SELECT clock_timestamp()','SELECT id,made_at,guidance_id,snapshot,p_below,p_within,p_above FROM earnings_live_predictions','SELECT pg_advisory_xact_lock','SELECT id,evidence_hash FROM earnings_live_results','INSERT INTO earnings_live_results')
        # store.insert uses psycopg Composed identifiers; inspect its rendered SQL.
        if not q.startswith(allowed):
            q=query.as_string(self.conn) if hasattr(query,'as_string') else q
            if not any(q.startswith('INSERT INTO '+name) for name in ('"earnings_actuals"','earnings_actual_edges')):raise AssertionError('Non-scratch scoring SQL rejected')
        return self.conn.execute(query,params)
    def transaction(self):return self.conn.transaction()

def rehearse(copy,output):
    data=read_copy(copy);selected=cases(data);details=[]
    with tempfile.TemporaryDirectory(prefix='crosscheck-score-reviews-') as directory,store.connect() as conn:
        try:
            setup(conn);created=conn.execute('SELECT clock_timestamp()').fetchone()[0]
            for row,b,asof in selected:
                source=row['source_record'];g=next(g for g in source['guidance_versions'] if g['id']==row['guidance_id']);review=review_for(row)
                for method in (b,smoothed_baseline.from_empirical(b)):
                    uid=str(uuid5(NS,row['id']+method['method_version']));p=method['probabilities']
                    fixture={'historical_asof':asof.isoformat(),'guidance_id':g['id'],'snapshot':{'locked_guidance':g},**{'p_'+k:str(v) for k,v in p.items()}}
                    conn.execute('INSERT INTO scratch_scoring_inputs(id,payload) VALUES(%s,%s)',(uid,Jsonb(fixture)))
                    Path(directory,uid+'.json').write_text(dumps(review)+'\n')
                    details.append({'scratch_id':uid,'observation_id':row['id'],'company':row['company'],'period_start':row['period_start'],'period_end':row['period_end'],'historical_asof_selection_coordinate':asof.isoformat(),'method':method['method_version'],'guidance_id':g['id'],'guidance_low':g['low'],'guidance_high':g['high'],'actual':source['actual'],'result_source':review['result_source'],'expected_outcome':row['outcome'],'probabilities':plain(p),'historical_ids':method['historical_ids']})
            wrapper=ScratchOnly(conn);first=score_live.run(wrapper,Path(directory));second=score_live.run(wrapper,Path(directory))
            assert not first['blocked'] and len(first['scored'])==6 and all(r['inserted'] for r in first['scored'])
            assert not second['blocked'] and all(r['inserted'] is None for r in second['scored'])
            scored={str(r[0]):r for r in conn.execute('SELECT prediction_id,outcome,brier,scored_at FROM pg_temp.earnings_live_results')}
            for d in details:
                r=scored[d['scratch_id']];assert r[1]==d['expected_outcome'];d.update(outcome=r[1],brier=str(r[2]),scratch_scored_at=r[3].astimezone(timezone.utc).isoformat())
            # Exercise the frozen SQL Brier guard with an incorrect score, scratch only.
            fixture=score_live.prediction_rows(wrapper)[0];review=json.loads(Path(directory,fixture['id']+'.json').read_text());ev=score_live.evaluate(fixture,review,datetime.now(timezone.utc))
            import psycopg
            rejected=False
            try:
                with conn.transaction():score_live.save(wrapper,fixture['id'],{**ev,'evidence_hash':'scratch-forged-brier','brier':baseline.Decimal(0) if ev['brier']!=0 else baseline.Decimal(1)})
            except psycopg.Error as exc:rejected='Incorrect unscaled multiclass Brier score' in str(exc)
            assert rejected
            result={'kind':'HISTORICAL_SCORING_REHEARSAL_NOT_LIVE_NOT_PREDICTIVE_EVALUATION','executed_at':datetime.now(timezone.utc).isoformat(),'scratch_created_at':created.astimezone(timezone.utc).isoformat(),'source_copy':str(copy),'source_copy_sha256':data['content_sha256'],'live_ledger_mutations':0,'prediction_rows_created':0,'scratch_namespace':'session-local TEMP tables/view, rolled back and dropped on disconnect','historical_asof_semantics':'Selection coordinates in retrospective fixture payloads only, not database creation timestamps; no live prediction or recording timestamp is backdated.','frozen_functions':['verify_sources','evaluate','save','run'],'frozen_result_guard_body_reused':True,'repeated_run_new_scores':0,'incorrect_brier_rejected':True,'scored_cases':details,'limitations':['Cases selected using known labels for below/within/above coverage; not performance measurement.','Existing source-curated/agent-reviewed comparability labels; no new owner outcome review claimed.','Retrospective probabilities filter SEC availability but use today-curated history; no prospective or calibrated quality claim.','Log score absent from frozen rules and implementation; not invented here.']}
            output.parent.mkdir(parents=True,exist_ok=True)
            with output.open('x') as f:f.write(dumps(result)+'\n')
        finally:conn.rollback()
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--copy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=rehearse(a.copy,a.output);print(dumps({'cases':len(r['scored_cases']),'live_mutations':0,'output':str(a.output)}))
