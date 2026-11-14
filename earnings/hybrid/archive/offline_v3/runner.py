"""Authorized diagnostic-only runner; fails before client construction by default."""
import argparse,fcntl,hashlib,json,os,time,uuid
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from pathlib import Path
from importlib.metadata import version
from .prepare import ROOT,DATA,read,write,digest
from .schema import Extraction
from .ledger import Ledger,Gate
from .transport import dispatch
from .validation import validate

LEDGER=DATA/'cost.sqlite3'
PINNED={'provider':'google_vertex_ai','project':'just-rhythm-506202-j8','location':'global','model':'gemini-3.6-flash','sdk':'google-genai==2.34.0'}

def configuration():
    c=read(ROOT/'config.json')
    if any(c[k]!=v for k,v in PINNED.items()) or version('google-genai')!='2.34.0':raise Gate('PINNED_EXECUTION_CONFIG_MISMATCH')
    limits={'temperature':0,'http_timeout_ms':300000,'wall_timeout_seconds':300,'sdk_attempts':1,'max_attempts_per_item':3,'max_concurrency':2,'max_input_tokens_documented':1048576,'ceiling_usd':'15.00','accounting_input_usd_per_million':'1.50','accounting_output_including_thinking_usd_per_million':'7.50','deadline':'2026-11-17T18:00:00-08:00'}
    if any(c.get(k)!=v for k,v in limits.items()):raise Gate('PINNED_SAFETY_LIMIT_MISMATCH')
    return c

def execution_fingerprint(c):
    # Provider is metadata, deliberately NOT a cache-key component.
    files=['prompt.txt','schema.py','prepare.py','validation.py','evidence.py','wire.py','transport.py','diagnostic_manifest.json','fresh_manifest.json']
    return digest(json.dumps({'config':c,'files':{f:digest((ROOT/f).read_bytes()) for f in files},'schema':Extraction.model_json_schema(),'calendar_dependencies':{str(f):digest(f.read_bytes()) for f in [ROOT.parent/'pilot_s5/calendars.json',ROOT.parent/'pilot_s5/calendar.py',ROOT.parent/'extraction/calendars.json',ROOT.parent/'extraction/rules.py']}},sort_keys=True).encode())

def check_prompt_freeze(c):
    p=read(ROOT/'prompt_freeze.json')
    if p['prompt_version']!=c['prompt_version'] or p['execution_fingerprint']!=execution_fingerprint(c):raise Gate('PROMPT_OR_EXECUTION_CHANGED_BUMP_VERSION_AND_FREEZE')

def key_for(input_hash,c):return digest(json.dumps([input_hash,c['model'],c['prompt_version']],separators=(',',':')).encode())

def cache_read(path,c,input_hash):
    if not path.exists():return None
    cached=read(path)
    if cached['provider']!=c['provider'] or cached['execution_fingerprint']!=execution_fingerprint(c) or cached['input_hash']!=input_hash or cached['requested_model']!=c['model'] or cached['prompt_version']!=c['prompt_version']:raise Gate('CACHE_EXECUTION_MISMATCH')
    if digest(json.dumps(cached['result'],sort_keys=True).encode())!=cached['result_sha256']:raise Gate('CACHE_INTEGRITY_FAILURE')
    return cached

def cache_write(path,c,input_hash,result):
    data={**PINNED,'requested_model':c['model'],'prompt_version':c['prompt_version'],'input_hash':input_hash,'execution_fingerprint':execution_fingerprint(c),'execution_config':c,'result':result,'result_sha256':digest(json.dumps(result,sort_keys=True).encode()),'created_at':datetime.now(timezone.utc).isoformat()}
    temporary=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');write(temporary,data)
    with temporary.open('rb') as f:os.fsync(f.fileno())
    os.replace(temporary,path)

def price_gate(c,pricing,clock):
    checked=datetime.fromisoformat(pricing['checked_at'])
    if not timedelta(0)<=clock-checked<=timedelta(hours=6):raise Gate('REFRESH_OFFICIAL_VERTEX_PRICING_REVIEW')
    if pricing['model']!=c['model'] or pricing['provider']!=c['provider']:raise Gate('WRONG_PRICE_MODEL_PROVIDER')
    if Decimal(pricing['input_upper_usd_per_million'])>Decimal('1.50') or Decimal(pricing['output_including_thinking_upper_usd_per_million'])>Decimal('7.50'):raise Gate('PRICING_EXCEEDS_ACCOUNTING_RATES')


def preflight(c,clock=None):
    clock=clock or datetime.now(timezone.utc);check_prompt_freeze(c)
    deadline=datetime.fromisoformat(c['deadline'])
    if clock+timedelta(seconds=1811)>=deadline:raise Gate('DEADLINE_RETRY_ALLOWANCE')
    authpath=ROOT/'inference_authorization.json'
    if not authpath.exists():raise Gate('NO_EXPLICIT_INFERENCE_AUTHORIZATION')
    auth=read(authpath)
    if auth.get('concurrent_deals_run_authorized') is not True or auth.get('residual_billing_uncertainty_accepted') is not True or auth.get('stage')!='diagnostic_only' or auth.get('confirmed_by')!='owner' or not auth.get('exact_user_confirmation'):raise Gate('NO_EXPLICIT_INFERENCE_AUTHORIZATION')
    stamp=datetime.fromisoformat(auth['recorded_at'])
    if stamp.tzinfo is None or stamp>clock:raise Gate('INVALID_AUTHORIZATION_TIMESTAMP')
    if c.get('live_authorization')!='OWNER_AUTHORIZED_CONCURRENT_DIAGNOSTICS':raise Gate('OFFLINE_CORRECTION_NO_NEW_INFERENCE')
    if c.get('reservation_policy')!='owner_approved_conservative_estimate_not_provider_cap' or c.get('output_reservation_multiplier')!=2:raise Gate('UNAPPROVED_RESERVATION_POLICY')
    pricing=read(ROOT/'pricing_review.json');price_gate(c,pricing,clock)
    return auth,pricing

def calendar_for(company):
    pilot=read(ROOT.parent/'pilot_s5/calendars.json')['registrations']
    matches=[x for x in pilot if x['company']==company]
    if matches:
        from earnings.pilot_s5.calendar import resolve
        return lambda y,q:resolve(matches[0],y,q)
    from earnings.extraction.rules import period
    return lambda y,q:period(company,y,q)

def process_case(case,c,ledger,*,send=dispatch,count_send=None,sleep=time.sleep,is_probe=False):
    inputpath=Path(case['input_path']);raw=inputpath.read_bytes()
    if digest(raw)!=case['input_sha256']:raise Gate('DIAGNOSTIC_INPUT_CHANGED')
    item=json.loads(raw);docs=item['documents']
    fresh={i['company'] for i in read(ROOT/'fresh_manifest.json')['issuers']}
    if case['company'] in fresh or any(d['company'] in fresh for d in docs):raise Gate('FRESH_INFERENCE_EMBARGO')
    payload=json.dumps({'documents':docs},sort_keys=True,separators=(',',':'))
    if len(payload.encode())>c['max_request_utf8_bytes']:return {'case_id':case['id'],'status':'INPUT_TOO_LARGE_NO_TRUNCATION','inference_performed':False}
    ih=digest(payload.encode());key=key_for(ih,c);cache=DATA/'responses';cache.mkdir(parents=True,exist_ok=True);path=cache/(key+'.json')
    with (cache/(key+'.lock')).open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        cached=cache_read(path,c,ih)
        if cached:
            with ledger.connect() as conn:ledger.event(conn,None,'cache_hit',{'cache_key':key,'provider':c['provider'],'inference_performed':False})
            return {'case_id':case['id'],'cache_status':'hit','result':cached['result'],'inference_performed':False}
        preflight(c)
        if is_probe and any(json.loads(r['metadata']).get('is_probe') for r in ledger.summary()['records']):raise Gate('PROBE_ALREADY_ATTEMPTED_STOP')
        for _ in range(1 if is_probe else 3):
            preflight(c)
            with ledger.connect() as conn:prior_count=conn.execute('SELECT count(*) FROM attempts WHERE item=?',(key,)).fetchone()[0]
            if prior_count>=(1 if is_probe else 3):raise Gate('RETRIES_EXHAUSTED')
            count_id=uuid.uuid4().hex;counter=count_send or dispatch
            with ledger.connect() as conn:ledger.event(conn,None,'count_requested',{'case_id':case['id'],'count_id':count_id,'known_cost_usd':'0','pricing_source':'official Vertex CountTokens documentation','input_hash':ih})
            counted=counter({**c,'_operation':'count'},(ROOT/'prompt.txt').read_text(),payload,DATA/(count_id+'-count.json'))
            write(DATA/(count_id+'-count-result.json'),counted)
            tokens=counted.get('counted_input_tokens')
            with ledger.connect() as conn:ledger.event(conn,None,'count_completed',{'case_id':case['id'],'count_id':count_id,'result':counted,'known_cost_usd':'0'})
            if counted['status']!='count_response' or type(tokens) is not int or not 0<tokens<=c['max_input_tokens_documented']:raise Gate('PROVIDER_COUNT_FAILED_STOP')
            aid=ledger.reserve(key,c,{'case_id':case['id'],**PINNED,'cache_status':'miss','input_hash':ih,'prompt_version':c['prompt_version'],'execution_fingerprint':execution_fingerprint(c),'count_id':count_id,'counted_input_tokens':tokens,'is_probe':is_probe})
            try:preflight(c)
            except Exception:
                ledger.finish(aid,{'prompt_token_count':0,'candidates_token_count':0,'thoughts_token_count':0,'total_token_count':0},state='cancelled_before_dispatch');raise
            write(DATA/(aid+'-request.json'),{'provider':c['provider'],'requested_model':c['model'],'project':c['project'],'location':c['location'],'execution_config':c,'execution_fingerprint':execution_fingerprint(c),'prompt_version':c['prompt_version'],'system_prompt':(ROOT/'prompt.txt').read_text(),'response_schema':Extraction.model_json_schema(),'input_hash':ih,'payload':json.loads(payload),'count_id':count_id,'counted_input_tokens':tokens,'is_probe':is_probe})
            with ledger.connect() as conn:ledger.event(conn,aid,'dispatch_intent',{'requested_model':c['model'],'provider':c['provider'],'is_probe':is_probe})
            started=time.monotonic()
            try:result=send(c,(ROOT/'prompt.txt').read_text(),payload,DATA/(aid+'-raw.json'))
            except Exception as exc:result={'status':'parent_dispatch_error_unknown_usage','usage':None,'returned_model_version':None,'http_code':None,'error_class':type(exc).__name__}
            result.setdefault('latency_seconds',str(time.monotonic()-started))
            ledger.finish(aid,result.get('usage'),state=result['status'],metadata={'returned_model_version':result.get('returned_model_version'),'http_code':result.get('http_code'),'error_class':result.get('error_class')})
            row=next(r for r in ledger.summary()['records'] if r['id']==aid)
            result.update(attempt_id=aid,provider=c['provider'],requested_model=c['model'],project=c['project'],location=c['location'],input_hash=ih,prompt_version=c['prompt_version'],counted_input_tokens=tokens,is_probe=is_probe,accounted_nano=row['accounted_nano'],reserved_nano=row['reserved_nano'],held_nano=row['held_nano'])
            write(DATA/(aid+'-result.json'),result)
            returned=result.get('returned_model_version')
            if returned and returned!=c['model'] and not returned.startswith(c['model']+'-'):
                with ledger.connect() as conn:conn.execute('INSERT INTO halt(reason) VALUES(?)',('UNEXPECTED_RETURNED_MODEL_VERSION',))
                raise Gate('UNEXPECTED_RETURNED_MODEL_VERSION')
            if result['status']=='response':
                try:result['validation']=validate(json.loads(result.get('text') or ''),docs,calendar_for(case['company']))
                except (ValueError,TypeError) as exc:result['validation']={'status':'INVALID_STRUCTURED_OUTPUT','error_class':type(exc).__name__,'quarantined':True}
                cache_write(path,c,ih,result)
                if row['accounted_nano'] is None:raise Gate('SUCCESS_RESPONSE_USAGE_UNKNOWN_OR_INCONSISTENT_STOP')
                if row['accounted_nano']>500_000_000 or ledger.summary()['halted']:raise Gate('ATTEMPT_COST_OR_CONTROL_LIMIT_STOP')
                if result['usage']['prompt_token_count']>tokens+c['input_reservation_margin_tokens']:raise Gate('PROVIDER_INPUT_COUNT_UNDERESTIMATE_STOP')
                return {'case_id':case['id'],'cache_status':'miss','result':result,'inference_performed':True}
            if is_probe:raise Gate('PROBE_FAILED_NO_RETRIES')
            code=result.get('http_code')
            if code in (400,401,403,404):
                with ledger.connect() as conn:conn.execute('INSERT INTO halt(reason) VALUES(?)',('MODEL_ACCESS_OR_CONFIGURATION_UNSUPPORTED',))
                raise Gate('MODEL_ACCESS_OR_CONFIGURATION_UNSUPPORTED_NO_SUBSTITUTION')
            transient=code in (408,429,500,502,503,504) or result['status'] in ('timeout_unknown_usage','worker_failed_unknown_usage') or result.get('error_class') in ('TimeoutException','ReadTimeout','ConnectTimeout','ConnectError','TransportError')
            with ledger.connect() as conn:count=conn.execute('SELECT count(*) FROM attempts WHERE item=?',(key,)).fetchone()[0]
            if not transient or count>=3:
                if code==429:raise Gate('SUSTAINED_THROTTLING_PAUSED')
                return {'case_id':case['id'],'status':'FAILED_RETRIES_EXHAUSTED' if transient else 'FAILED_NONRETRYABLE','inference_performed':True,'last_attempt_id':aid}
            sleep(c['retry_backoff_seconds'][count-1])
        return {'case_id':case['id'],'status':'FAILED','inference_performed':True}


def probe_gate(item):
    result=item.get('result',{})
    if result.get('status')!='response' or result.get('accounted_nano') is None:raise Gate('PROBE_USAGE_OR_RESPONSE_GATE_FAILED')
    returned=result.get('returned_model_version')
    if not returned or returned!='gemini-3.6-flash' and not returned.startswith('gemini-3.6-flash-'):raise Gate('PROBE_MODEL_VERSION_GATE_FAILED')
    if result['accounted_nano']>500_000_000:raise Gate('PROBE_COST_GATE_FAILED')
    if result.get('validation',{}).get('status')=='INVALID_STRUCTURED_OUTPUT':raise Gate('PROBE_STRUCTURED_OUTPUT_GATE_FAILED')
    if not result.get('finish_reasons') or any(x!='STOP' for x in result['finish_reasons']):raise Gate('PROBE_FINISH_REASON_GATE_FAILED')


def run(probe_only=False):
    c=configuration();ledger=Ledger(LEDGER);result=[];started=datetime.now(timezone.utc).isoformat();before=ledger.summary()['attempts'];stopped=None;passed=False
    try:
        check_prompt_freeze(c)
        for index,case in enumerate(read(ROOT/'diagnostic_manifest.json')['cases']):
            try:
                item=process_case(case,c,ledger,is_probe=index==0);result.append(item)
                if index==0:
                    probe_gate(item);passed=True
                    write(DATA/'probe_control.json',{'passed':True,'recorded_at':datetime.now(timezone.utc).isoformat(),'result':item,'operational_evidence_only':True,'provider_billing_cap_guaranteed':False})
                    if probe_only:break
            except Gate as exc:
                if index>0 and str(exc) in ('RETRIES_EXHAUSTED','ITEM_ALREADY_IN_FLIGHT'):
                    result.append({'case_id':case['id'],'status':str(exc)});continue
                raise
    except Gate as exc:stopped=str(exc)
    summary=ledger.summary();target=DATA/('run-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    write(target,{'stage':'diagnostic_only','probe_only':probe_only,'probe_passed':passed,'started_at':started,'finished_at':datetime.now(timezone.utc).isoformat(),'stopped_reason':stopped,'results':result,'cost_ledger':summary,'inference_attempts_this_run':summary['attempts']-before,'inference_performed':summary['attempts']>before,'human_review_complete':False,'ledger_ceiling_not_provider_billing_cap':True})
    return target

def dispatch_status(c,ledger):
    summary=ledger.summary()
    if summary['halted']:return 'EXPERIMENT_HALTED_REVIEW_REQUIRED'
    probes=[r for r in summary['records'] if json.loads(r['metadata']).get('is_probe')]
    if probes and probes[0]['accounted_nano'] is None:
        return 'PROBE_USAGE_UNRESOLVED_STOP_REVIEW_REQUIRED'
    try:preflight(c)
    except (Gate,FileNotFoundError) as exc:return str(exc)
    return 'AUTHORIZED_PROBE_REQUIRED' if not probes else 'PROBE_CONTROLS_REQUIRE_RECHECK'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['status','probe','run']);args=p.parse_args()
    if args.command=='status':
        c=configuration();ledger=Ledger(LEDGER)
        status=dispatch_status(c,ledger)
        print(json.dumps({'dispatch_status':status,'inference_performed':False,'configuration':PINNED,'budget':ledger.summary()},indent=2))
    else:
        try:print(run(probe_only=args.command=='probe'))
        except Gate as exc:print(json.dumps({'status':'BLOCKED','reason':str(exc),'budget':Ledger(LEDGER).summary()}));raise SystemExit(2)
