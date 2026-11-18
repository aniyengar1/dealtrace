"""Copy live records using a READ ONLY transaction; publish a sanitized JSON view.

python -m earnings.publication.export
The SQLite archive is private/local and self-contained. The web page reads only
predictions.json. No source mutations, scoring calls, or lock calls occur here.
"""
import argparse,json,sqlite3,os,tempfile
from pathlib import Path
from datetime import datetime,date,timezone
from decimal import Decimal
from uuid import UUID
from earnings import store
from earnings.models import digest,dumps,money

DEFAULT=Path(__file__).with_name('predictions.json')
COPIES=Path('data/cache/earnings/publication')

def packed(value):
    if isinstance(value,datetime):return value.astimezone(timezone.utc).isoformat()
    if isinstance(value,date):return value.isoformat()
    if isinstance(value,Decimal):return format(value,'f')
    if isinstance(value,UUID):return str(value)
    if isinstance(value,dict):return {k:packed(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [packed(v) for v in value]
    if isinstance(value,float):raise ValueError('Financial floats are forbidden')
    return value

def rows(conn,query):
    cur=conn.execute(query);keys=[d.name for d in cur.description]
    return [packed(dict(zip(keys,r))) for r in cur]

def capture(conn):
    conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
    conn.execute('SET LOCAL ROLE authenticated')
    stamp=conn.execute('SELECT clock_timestamp()').fetchone()[0]
    p=rows(conn,'SELECT p.*,c.ticker,c.name FROM earnings_live_predictions p JOIN companies c ON c.id=p.company_id ORDER BY p.id')
    r=rows(conn,'SELECT * FROM earnings_live_results ORDER BY id')
    h=rows(conn,'SELECT * FROM earnings_historical_observations ORDER BY id')
    content={'predictions':p,'results':r,'historical_observations':h}
    return {'schema_version':'crosscheck-ledger-copy-v1','exported_at':packed(stamp),'source_transaction_read_only':conn.execute('SHOW transaction_read_only').fetchone()[0],
            'content_sha256':digest(content),'ledger_sha256':digest({'predictions':p,'results':r}),**content}

def archive(data,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive reservation: never overwrite an earlier archive.
    with path.open('xb'):pass
    with sqlite3.connect(path) as c:
        for table in ('predictions','results','historical_observations'):
            c.execute(f'CREATE TABLE {table}(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            c.executemany(f'INSERT INTO {table} VALUES(?,?)',[(r['id'],dumps(r)) for r in data[table]])
        c.execute('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        c.executemany('INSERT INTO metadata VALUES(?,?)',[(k,json.dumps(v)) for k,v in data.items() if k not in ('predictions','results','historical_observations')])

def read_copy(path):
    with sqlite3.connect('file:'+str(path.resolve())+'?mode=ro',uri=True) as c:
        c.execute('PRAGMA query_only=ON')
        data={k:json.loads(v) for k,v in c.execute('SELECT key,value FROM metadata')}
        for table in ('predictions','results','historical_observations'):
            data[table]=[json.loads(r[0]) for r in c.execute(f'SELECT payload FROM {table} ORDER BY id')]
    if digest({k:data[k] for k in ('predictions','results','historical_observations')})!=data['content_sha256']:raise ValueError('Archive integrity mismatch')
    return data

def public_view(data):
    output=[]
    for p in data['predictions']:
        g=p['snapshot']['locked_guidance'];scores=sorted([r for r in data['results'] if r['prediction_id']==p['id']],key=lambda r:(r['scored_at'],r['id']))
        latest=scores[-1] if scores else None;actual=None
        if latest and latest['status']=='scored':
            review=latest['snapshot']['review'];a=review['actual'];actual={'value':format(money(a['value']),'f'),'unit':a['unit'],'period_start':a['start'],'period_end':a['end'],'accession':a['accession'],'filed':a['filed'],'source_url':review['result_source']['url']}
        output.append({'id':p['id'],'company':p['ticker'],'name':p['name'],'metric':p['metric'],'period_start':p['period_start'],'period_end':p['period_end'],
            'quarter':p['snapshot']['latest_registry_target']['label'],'guidance':{'id':p['guidance_id'],'low':format(money(g['low']),'f'),'high':format(money(g['high']),'f'),'unit':g['unit'],'basis':g['basis'],'source_url':g['source_url'],'accession':g['accession'],'filed':g['filed'],'quote':g['quote']},
            'method':p['method_version'],'locked_at':p['made_at'],'probabilities':{k:format(money(p['p_'+k]),'f') for k in ('below','within','above')},
            'sample_size':p['snapshot']['baseline']['sample_size'],'evidence_sha256':digest({k:p[k] for k in ('announcement','publication_check','snapshot')}),
            'evidence_hash_version':'earnings.models.digest sorted indent2 JSON over announcement/publication_check/snapshot, UTF-8',
            'announcement':{'source_url':p['announcement']['source_url'],'source_sha256':p['announcement']['source_sha256'],'release_date':p['announcement']['release_date'],'timezone':p['announcement']['timezone'],'verification_status':p['announcement']['verification_status']},
            'result':None if latest is None else {'id':latest['id'],'status':latest['status'],'outcome':latest['outcome'],'brier':latest['brier'],'scored_at':latest['scored_at'],'evidence_hash':latest['evidence_hash'],'supersedes_id':latest['supersedes_id'],'actual':actual},'score_versions':len(scores)})
    return {'schema_version':'crosscheck-public-predictions-v1','copied_at':data['exported_at'],'source':'READ ONLY export to separate local SQLite copy; web reads this JSON only','ledger_sha256':data['ledger_sha256'],'prediction_count':len(output),'predictions':sorted(output,key=lambda r:(r['announcement']['release_date'],r['company'],{'quarter-frequency-v1':0,'quarter-frequency-laplace-v1':1}.get(r['method'],2))),'scoring_policy':{'classification':'below < low; within inclusive; above > high','brier':'unscaled sum((p_k - indicator)^2), range0..2','log_score':'not defined or implemented in frozen checkpoint; no clipping policy'}}

def publish(data,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.predictions-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:f.write(dumps(public_view(data))+'\n')
        os.replace(tmp,path)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=DEFAULT);parser.add_argument('--copy-dir',type=Path,default=COPIES);a=parser.parse_args()
    with store.connect() as conn:
        try:data=capture(conn)
        finally:conn.rollback()
    name=data['exported_at'].replace(':','-')+'-'+data['content_sha256'][:12]+'.sqlite3';target=a.copy_dir/name
    archive(data,target);copied=read_copy(target);publish(copied,a.output)
    print(dumps({'copy':str(target),'public_snapshot':str(a.output),'predictions':len(data['predictions']),'results':len(data['results']),'source_read_only':data['source_transaction_read_only'],'ledger_sha256':data['ledger_sha256']}))
