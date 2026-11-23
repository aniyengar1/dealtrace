"""Synthetic scoring/publication rehearsal. Explicit private scratch DB only.

No locks are created: copied predictions are exposed through a TEMP view.
All fabricated source bytes are an in-memory transport fixture, never the SEC
cache. Production scoring code and SQL Brier guard run unchanged.
"""
import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from . import score_live, store
from .baseline import aware, day_available, ZoneInfo, ZONE
from .models import dumps, plain, digest, money
from .publication import export, snapshot_sql
from .actuals import Blocked
from .registry import companies

ROOT=Path(__file__).resolve().parent
LABEL='SYNTHETIC_SCORING_REHEARSAL_NOT_REPORTED_RESULTS'


def checked_scratch(dsn):
    options=conninfo_to_dict(dsn)
    if options.get('host') not in ('127.0.0.1','localhost','/tmp') or options.get('port')!='65439' or not options.get('dbname','').startswith('crosscheck_scoring_rehearsal_'):
        raise ValueError('Explicit private local scoring-rehearsal DSN required; never DATABASE_URL')
    conn=psycopg.connect(dsn,autocommit=True,options='-c default_transaction_read_only=on')
    if not conn.execute('SHOW data_directory').fetchone()[0].startswith('/tmp/crosscheck-snapshot-pg-'):
        conn.close();raise ValueError('Not the private temporary cluster')
    conn.execute('SET default_transaction_read_only=off')
    return conn


def synthetic_review(p, clock):
    g=p['snapshot']['locked_guidance'];c=companies()[p['ticker']]
    low,high=money(g['low']),money(g['high'])
    # Cover a zero-probability miss, both inclusive endpoints, and an above.
    value={'OKTA':low-money('1000000'),'CRM':low,'IOT':high+money('1000000'),'S':high}.get(p['ticker'],(low+high)/2)
    issued=(aware(p['made_at']).astimezone(ZoneInfo(ZONE)).date()+timedelta(days=1)).isoformat()
    available=day_available(issued)
    if available>clock:raise ValueError('No room for a synthetic post-lock publication before actual current time')
    accession=f"{c['cik']}-26-900001"
    url=f"https://www.sec.gov/Archives/edgar/data/{int(c['cik'])}/{accession.replace('-','')}/SYNTHETIC-REHEARSAL-ex991.htm"
    actual=store.actual_from({'company':p['ticker'],'concept':c['concept'],'start':g['start'],'end':g['end'],'value':str(value),'unit':g['unit'],'basis':g['basis'],'accession':accession,'filed':issued,'form':'10-Q','fiscal_year':2027,'fiscal_period':'Q3','source_url':f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c['cik']}.json",'parents':[],'derivation':None})
    date_quote=f'{issued} SYNTHETIC REHEARSAL ONLY - fabricated results, not an SEC filing.'
    quote=f'SYNTHETIC consolidated revenue for three months ended {g["end"]}: USD {value}.'
    review={'actual':{'id':actual.id,**plain(actual)},'actual_parents':[],
        'result_source':{'url':url,'accession':accession,'filed_date':issued,'issued_date':issued,'issuance_date_quote':date_quote,'quote':quote,'exhibit':'99.1'},
        'first_result_publication_lower_bound':datetime.combine(datetime.fromisoformat(issued).date(),datetime.min.time(),ZoneInfo(ZONE)).isoformat(),
        'evidence_available_at':available.isoformat(),
        'outcome_basis_review':{'actual_id':actual.id,'guidance_id':p['guidance_id'],'blocked':False,'available_on':clock.date().isoformat(),'reviewed_at':clock.isoformat(),'verifier':LABEL+' agent test fixture; NOT owner review','reason':LABEL+' same pinned period/unit/basis by construction','sources':[{'url':url,'filed_date':issued}]},
        'rehearsal_provenance':LABEL}
    literal=int(value) if value==value.to_integral_value() else format(value,'f')
    facts={'facts':{'us-gaap':{actual.concept:{'units':{actual.unit:[{'start':g['start'],'end':g['end'],'accn':accession,'filed':issued,'val':literal}]}}}}}
    return review,{actual.source_url:json.dumps(facts).encode(),url:f'<p>{date_quote}</p><p>{quote}</p>'.encode()}


def setup(conn,data):
    # Public migration objects exist only in the private, empty scratch DB.
    for name,table,key in [('prediction','earnings_live_predictions','predictions'),('history','earnings_historical_observations','historical_observations')]:
        conn.execute(f'CREATE TEMP TABLE scratch_{name}_copies(payload JSONB NOT NULL,fixture_kind TEXT NOT NULL DEFAULT \'{LABEL}\')')
        for row in data[key]:conn.execute(f'INSERT INTO scratch_{name}_copies(payload) VALUES(%s)',(Jsonb(row),))
        conn.execute(f'CREATE TEMP VIEW {table} AS SELECT (jsonb_populate_record(NULL::public.{table},payload)).* FROM scratch_{name}_copies')
    conn.execute('CREATE TEMP TABLE companies(id UUID PRIMARY KEY,ticker TEXT NOT NULL,name TEXT NOT NULL)')
    for p in {r['company_id']:r for r in data['predictions']}.values():conn.execute('INSERT INTO pg_temp.companies VALUES(%s,%s,%s)',(p['company_id'],p['ticker'],p['name']))
    for table in ('earnings_actuals','earnings_actual_edges','earnings_live_results'):
        conn.execute(f'CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)')
    body=re.search(r'CREATE FUNCTION earnings_result_guard\(\).*?AS \$\$(.*?)\$\$;',Path('db/migrations/0103_crosscheck_live_ledger.sql').read_text(),re.S).group(1)
    conn.execute('CREATE FUNCTION pg_temp.rehearsal_result_guard() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_temp,pg_catalog AS $$'+body+'$$')
    conn.execute('CREATE TRIGGER rehearsal_result_check BEFORE INSERT ON pg_temp.earnings_live_results FOR EACH ROW EXECUTE FUNCTION pg_temp.rehearsal_result_guard()')
    for table in ('earnings_live_predictions','earnings_live_results','earnings_historical_observations','companies','scratch_prediction_copies','scratch_history_copies'):
        conn.execute(f'GRANT SELECT ON pg_temp.{table} TO authenticated,service_role')
    for table in ('earnings_actuals','earnings_actual_edges','earnings_live_results'):
        conn.execute(f'GRANT INSERT,SELECT ON pg_temp.{table} TO service_role')
    conn.execute('SET search_path=pg_temp,pg_catalog')
    for table in ('earnings_live_predictions','earnings_live_results','earnings_actuals','earnings_actual_edges','companies','earnings_historical_observations'):
        assert conn.execute('SELECT to_regclass(%s)=to_regclass(%s)',(table,'pg_temp.'+table)).fetchone()[0]
    # No original live lock table rows exist, even in this scratch database.
    assert conn.execute('SELECT count(*) FROM public.earnings_live_predictions').fetchone()[0]==0


def rehearse(copy, output, dsn):
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT.parent/'data/cache/earnings/scoring-pipeline-rehearsal').resolve()):raise ValueError('Synthetic outputs require the ignored private scoring-pipeline-rehearsal cache')
    output.mkdir(parents=True,exist_ok=False)
    data=export.read_copy(Path(copy));timings={};started=datetime.now(timezone.utc)
    if data['results']:raise ValueError('This bounded first-scoring rehearsal expects a zero-score source copy')
    guard=checked_scratch(dsn);guard.close()
    from db.migrate import run as migrate
    before=time.monotonic();migrate(dsn);timings['scratch_migrations_seconds']=str(time.monotonic()-before)
    reviews=output/'reviews';reviews.mkdir();fixtures={};expected={}
    for p in data['predictions']:
        review,source=synthetic_review(p,started);fixtures.update(source)
        (reviews/(p['id']+'-SYNTHETIC.json')).write_text(dumps(review)+'\n')
        value=money(review['actual']['value']);g=p['snapshot']['locked_guidance']
        expected[p['id']]='below' if value<money(g['low']) else 'above' if value>money(g['high']) else 'within'
    def synthetic_fetch(url,**kwargs):
        if url not in fixtures:raise AssertionError('Unexpected source request; no real HTTP permitted in rehearsal')
        body=fixtures[url];return body,{'simulation':True,'sha256':hashlib.sha256(body).hexdigest(),'fetched_at':datetime.now(timezone.utc).isoformat()}
    conn=checked_scratch(dsn)
    try:
        setup(conn,data)
        before=time.monotonic()
        with patch('earnings.sec.fetch',synthetic_fetch):
            with conn.transaction():first=score_live.run(conn,reviews)
            with conn.transaction():second=score_live.run(conn,reviews)
        timings['score_and_repeat_seconds']=str(time.monotonic()-before)
        assert not first['blocked'],first['blocked']
        assert len(first['scored'])==len(data['predictions']) and all(r['inserted'] for r in first['scored'])
        assert not second['blocked'] and all(r['inserted'] is None for r in second['scored'])
        assert all(r['outcome']==expected[r['prediction_id']] for r in first['scored'])
        p=score_live.prediction_rows(conn)[0];review=json.loads((reviews/(p['id']+'-SYNTHETIC.json')).read_text())
        future={**review,'evidence_available_at':(started+timedelta(days=1)).isoformat()}
        try:score_live.evaluate(p,future,started)
        except Blocked as exc:assert exc.code=='MISSING_PERIOD'
        else:raise AssertionError('Future evidence incorrectly accepted')
        (output/'score-execution-SYNTHETIC.json').write_text(dumps(first)+'\n')
        before=time.monotonic()
        try:scored=export.capture(conn)
        finally:conn.rollback()
        assert scored['predictions']==data['predictions'],'Copied lock snapshots/timestamps changed'
        assert scored['historical_observations']==data['historical_observations']
        assert len(scored['results'])==len(data['predictions'])
        scored['simulation']=True
        archive=output/'SYNTHETIC-scored-copy.sqlite3';export.archive(scored,archive);copied=export.read_copy(archive)
        publication=output/'publication';publication.mkdir();export.publish(copied,publication/'predictions.json')
        payload=json.loads((publication/'predictions.json').read_text());payload.update(simulation=True,rehearsal_provenance=LABEL)
        (publication/'predictions.json').write_text(dumps(payload)+'\n')
        backtest=json.loads((ROOT/'publication/backtest.json').read_text());backtest['simulation']=True
        (publication/'backtest.json').write_text(dumps(backtest)+'\n')
        seed=snapshot_sql.script(publication,allow_synthetic=True);(publication/'SYNTHETIC-seed.sql').write_text(seed)
        conn.execute((ROOT/'sql/published_snapshots.sql').read_text());conn.execute(seed);conn.execute(seed)
        with conn.transaction():
            conn.execute('SET LOCAL ROLE dealtrace_web')
            served=conn.execute("SELECT payload FROM public.crosscheck_prediction_snapshots WHERE snapshot_id='current'").fetchone()[0]
            assert served==payload and len(served['predictions'])==len(data['predictions'])
            assert all(r['result']['status']=='scored' and r['score_versions']==1 for r in served['predictions'])
            assert conn.execute("SELECT payload FROM public.crosscheck_backtest_snapshots WHERE snapshot_id='current'").fetchone()[0]==backtest
        timings['archive_export_seed_and_read_seconds']=str(time.monotonic()-before)
        for table in ('crosscheck_prediction_snapshots','crosscheck_backtest_snapshots'):
            for query in [f'INSERT INTO public.{table} SELECT * FROM public.{table}',f'DELETE FROM public.{table}',f'TRUNCATE public.{table}',f'UPDATE public.{table} SET published_at=clock_timestamp()']:
                try:
                    with conn.transaction():conn.execute('SET LOCAL ROLE dealtrace_web');conn.execute(query)
                except psycopg.errors.InsufficientPrivilege:pass
                else:raise AssertionError('Publication reader could mutate a copy')
        assert conn.execute('SELECT count(*) FROM public.earnings_live_predictions').fetchone()[0]==0
        assert conn.execute('SELECT count(*) FROM public.earnings_live_results').fetchone()[0]==0
    finally:conn.close()
    result={'kind':LABEL,'started_at':started.isoformat(),'finished_at':datetime.now(timezone.utc).isoformat(),'source_ledger_sha256':data['ledger_sha256'],'source_predictions':len(data['predictions']),'scratch_scores':len(first['scored']),'duplicate_repeat_insertions':sum(r['inserted'] is not None for r in second['scored']),'future_evidence_blocked':True,'copied_locks_and_history_unchanged':True,'scratch_seed_idempotent':True,'snapshot_select_only_enforced':True,'source_transport':'in-memory synthetic SEC responses only; no real HTTP or cache writes','publication':'private synthetic SQL guard; no production JSON/seed changed','timings_seconds':timings,'outcomes':first['scored'],'synthetic_actuals_by_company':{p['ticker']:json.loads((reviews/(p['id']+'-SYNTHETIC.json')).read_text())['actual']['value'] for p in data['predictions']},'manual_review':'NOT PERFORMED; synthetic agent fixtures only; source semantics and first-publication evidence still require owner review on real scoring day'}
    (output/'REHEARSAL-RESULT.json').write_text(dumps(result)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--copy',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    dsn=os.environ.get('CROSSCHECK_REHEARSAL_DATABASE_URL')
    if not dsn:p.error('Explicit CROSSCHECK_REHEARSAL_DATABASE_URL required; DATABASE_URL is never used')
    print(dumps(rehearse(a.copy,a.output,dsn)))
