"""Local/mocked experiment tests. No ADC or live Vertex calls allowed."""
import json,socket,time
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import pytest
from earnings.hybrid import ledger,runner,transport
from earnings.hybrid.prepare import ROOT,read,write
from earnings.hybrid.validation import validate

@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*a,**kw):raise AssertionError('Hybrid tests forbid network access')
    monkeypatch.setattr(socket.socket,'connect',denied)
    monkeypatch.setattr(socket,'create_connection',denied)

@pytest.fixture
def c():
    result=runner.configuration();result.update(billable_thinking_bound_verified=True,max_input_tokens_documented=10000,max_billable_output_tokens=8192)
    return result # synthetic verified bounds for tests only; real config false

STAMP=datetime(2026,11,13,12,tzinfo=timezone.utc)

def test_real_configuration_blocks_unverified_bounds_without_charge(tmp_path):
    l=ledger.Ledger(tmp_path/'ledger.sqlite');real=runner.configuration()
    with pytest.raises(ledger.Gate,match='UNVERIFIED_BILLABLE_THINKING_BOUND'):l.reserve('x',real,{},STAMP)
    assert l.summary()['attempts']==0

def test_thinking_is_separate_and_cached_input_not_added_twice(tmp_path,c):
    l=ledger.Ledger(tmp_path/'l');aid=l.reserve('x',c,{},STAMP)
    l.finish(aid,{'prompt_token_count':100,'candidates_token_count':10,'thoughts_token_count':20,'total_token_count':130,'cached_content_token_count':80})
    assert l.summary()['known_accounted_usd']=='0.000375'
    assert l.summary()['outstanding_unknown_or_active_reservations_usd']=='0'

def test_missing_thinking_count_retains_full_reservation(tmp_path,c):
    l=ledger.Ledger(tmp_path/'l');aid=l.reserve('x',c,{},STAMP)
    l.finish(aid,{'prompt_token_count':100,'candidates_token_count':10,'total_token_count':130})
    assert l.summary()['known_accounted_usd']=='0'
    assert Decimal(l.summary()['outstanding_unknown_or_active_reservations_usd'])>0

def test_inconsistent_total_retains_reservation(tmp_path,c):
    l=ledger.Ledger(tmp_path/'l');aid=l.reserve('x',c,{},STAMP)
    l.finish(aid,{'prompt_token_count':100,'candidates_token_count':10,'thoughts_token_count':20,'total_token_count':110})
    assert l.summary()['records'][0]['accounted_nano'] is None

def test_atomic_budget_unknown_failures_and_retry_charge(tmp_path,c):
    c.update(max_input_tokens_documented=1000000,max_billable_output_tokens=1000000)
    l=ledger.Ledger(tmp_path/'l');aid=l.reserve('x',c,{},STAMP);l.finish(aid,None,state='timeout')
    assert l.summary()['total_held_usd']=='9'
    with pytest.raises(ledger.Gate,match='BUDGET_LIMIT'):l.reserve('x',c,{},STAMP)

def test_concurrency_shared_across_independent_connections(tmp_path,c):
    path=tmp_path/'l';ledger.Ledger(path)
    def attempt(i):
        try:return ledger.Ledger(path).reserve(str(i),c,{},STAMP)
        except ledger.Gate:return None
    with ThreadPoolExecutor(max_workers=8) as pool:result=list(pool.map(attempt,range(8)))
    assert sum(x is not None for x in result)==2
    assert ledger.Ledger(path).summary()['active_attempts']==2

def test_retry_count_does_not_reset_on_resume(tmp_path,c):
    path=tmp_path/'l'
    for _ in range(3):
        l=ledger.Ledger(path);aid=l.reserve('x',c,{},STAMP);l.finish(aid,None,state='failure')
    with pytest.raises(ledger.Gate,match='RETRIES_EXHAUSTED'):ledger.Ledger(path).reserve('x',c,{},STAMP)
    assert l.summary()['attempts']==3

def test_no_dispatch_at_deadline_even_when_money_available(tmp_path,c):
    l=ledger.Ledger(tmp_path/'l');deadline=datetime.fromisoformat(c['deadline'])
    with pytest.raises(ledger.Gate,match='DEADLINE'):l.reserve('x',c,{},deadline-timedelta(seconds=900))
    assert l.summary()['attempts']==0

def test_events_append_only_and_unexpected_usage_halts(tmp_path,c):
    l=ledger.Ledger(tmp_path/'l');aid=l.reserve('x',c,{},STAMP)
    l.finish(aid,{'prompt_token_count':1000000,'candidates_token_count':100000,'thoughts_token_count':0,'total_token_count':1100000})
    assert l.summary()['halted']
    with pytest.raises(ledger.Gate,match='HALTED'):l.reserve('next',c,{},STAMP)
    with l.connect() as conn:
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):conn.execute('DELETE FROM events')

def test_sdk_config_units_retries_continuation_and_explicit_provider(c):
    captured={}
    def factory(**kw):captured.update(kw);return object()
    _,g=transport.make_client(c,factory)
    assert captured['vertexai'] is True and captured['project']=='just-rhythm-506202-j8' and captured['location']=='global' and captured['api_key'] is None
    http=captured['http_options'];assert http.timeout==300000 and http.retry_options.attempts==1
    assert g.response_mime_type=='application/json' and g.response_schema is not None
    assert g.temperature==0 and g.automatic_continuation is False and g.automatic_function_calling.disable is True

def test_actual_sdk_mock_transport_does_not_retry_429(c,monkeypatch):
    # Real SDK, anonymous MOCK credentials, local httpx handler, socket denied.
    import httpx
    from google import genai
    from google.genai import types,errors
    from google.oauth2.credentials import Credentials
    monkeypatch.delenv("GOOGLE_API_KEY",raising=False);monkeypatch.delenv("GEMINI_API_KEY",raising=False)
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(429,json={'error':{'code':429,'status':'RESOURCE_EXHAUSTED','message':'synthetic'}})
    client=genai.Client(vertexai=True,project=c['project'],location='global',credentials=Credentials(token='synthetic-test-not-a-secret'),http_options=types.HttpOptions(timeout=300000,retry_options=types.HttpRetryOptions(attempts=1),client_args={'transport':httpx.MockTransport(handler)}))
    with client:
        with pytest.raises(errors.ClientError):client.models.generate_content(model=c['model'],contents='synthetic local test',config=types.GenerateContentConfig(automatic_continuation=False))
    assert len(calls)==1

def test_preflight_never_constructs_client_before_owner_confirmation(monkeypatch):
    monkeypatch.setattr(runner,'check_prompt_freeze',lambda c:None)
    monkeypatch.setattr(transport,'make_client',lambda *a,**k:pytest.fail('Client constructed'))
    with pytest.raises(ledger.Gate,match='WAITING_EXPLICIT_OWNER'):runner.preflight(runner.configuration(),STAMP)

def test_cache_key_excludes_provider_but_rejects_mismatched_execution(tmp_path,c):
    other={**c,'provider':'different'};assert runner.key_for('input',c)==runner.key_for('input',other)
    path=tmp_path/'cache';runner.cache_write(path,c,'input',{'ok':True})
    assert runner.cache_read(path,c,'input')['result']=={'ok':True}
    with pytest.raises(ledger.Gate,match='CACHE_EXECUTION_MISMATCH'):runner.cache_read(path,other,'input')
    altered=read(path);altered['result']['ok']=False;write(path,altered)
    with pytest.raises(ledger.Gate,match='CACHE_INTEGRITY'):runner.cache_read(path,c,'input')

def fixture():
    text='For the third quarter fiscal2026 consolidated reported USD revenue is $2.40 billion +/- $100 million. Issued May20,2026.'
    doc={'source_id':'current','company':'TEST','filed':'2026-05-20','canonical_text':text,'tables':[]}
    roles=['metric','scope','period','units','basis','guidance_type','amount','issuance']
    obs={'source_id':'current','metric_label':'revenue','metric_class':'consolidated_revenue','scope':'consolidated','scope_support':'explicit','basis_kind':'reported','scope_qualifiers':[],'fiscal_year':2026,'fiscal_quarter':3,'period_start':'2026-05-01','period_end':'2026-07-31','issued_start':'2026-05-20','issued_end':'2026-05-20','issued_precision':'day','currency':'USD','guidance_type':'direct','amount_style':'absolute_tolerance','low':None,'high':None,'center':{'value':'2.40','scale':'1000000000'},'tolerance':{'value':'100','scale':'1000000'},'status':'initial','status_support':'first_observed_quarter','prior_observation_index':None,'table_id':None,'column_label':None,'table_row_index':None,'table_column_index':None,'evidence':[{'source_id':'current','start':0,'end':len(text),'quote':text,'role':r} for r in roles],'review_note':'synthetic, not real guidance'}
    return {'observations':[obs],'unresolved_sections':[]},[doc]

def cal(y,q):return '2026-05-01','2026-07-31'

def test_decimal_tolerance_and_no_semantic_or_human_approval():
    data,docs=fixture();r=validate(data,docs,cal)['observations'][0]
    assert not r['deterministic_errors'] and r['normalized_low']=='2300000000.00' and r['normalized_high']=='2500000000.00'
    assert r['quarantined'] and r['review_status']=='human_review_pending' and r['semantic_validation']=='NOT_GUARANTEED'

@pytest.mark.parametrize('field,value,reason',[('metric_class','arr','NONELIGIBLE'),('scope','segment','NONELIGIBLE'),('guidance_type','implied','NONELIGIBLE'),('amount_style','percentage_tolerance','NON_ABSOLUTE'),('period_end','2026-08-01','CALENDAR_BOUNDARY'),('issued_end','2026-05-21','PUBLIC_AVAILABILITY'),('status','unresolved','UNRESOLVED_STATUS')])
def test_rejects_unsupported_interpretations(field,value,reason):
    d,docs=fixture();d['observations'][0][field]=value
    assert any(reason in e for e in validate(d,docs,cal)['observations'][0]['deterministic_errors'])

def test_quote_checks_do_not_approve_semantics_and_missing_money_stays_missing():
    d,docs=fixture();d['observations'][0]['evidence'][0]['quote']='invented'
    assert 'QUOTE_OFFSET_MISMATCH' in validate(d,docs,cal)['observations'][0]['deterministic_errors']
    d,docs=fixture();o=d['observations'][0];o['amount_style']='range';o['center']=o['tolerance']=None
    r=validate(d,docs,cal)['observations'][0];assert r['normalized_low'] is None and 'MISSING_AMOUNT' in r['deterministic_errors']

def test_status_cannot_borrow_arr_or_future_target():
    d,docs=fixture();prior=deepcopy(d['observations'][0]);prior['source_id']='prior';prior['metric_class']='arr';d['observations'][0].update(status='reaffirmed',status_support='prior_range',prior_observation_index=1);d['observations'].append(prior)
    docs.append({**docs[0],'source_id':'prior','filed':'2026-06-01'})
    errors=validate(d,docs,cal)['observations'][0]['deterministic_errors']
    assert 'INCOMPARABLE_STATUS_REFERENCE' in errors and 'FUTURE_OR_SAME_RELEASE_STATUS_REFERENCE' in errors

def test_fresh_manifest_and_human_review_stay_unopened():
    manifest=read(ROOT/'fresh_manifest.json');rows=[r for i in manifest['issuers'] for r in i.get('releases',[])]
    assert len(rows)==36 and all(not r['release_body_opened'] and not r['labels_created'] and not r['inference_performed'] for r in rows)
    diag=read(ROOT/'diagnostic_manifest.json');assert not ({c['company'] for c in diag['cases']}&{i['company'] for i in manifest['issuers']})
    packet=read(ROOT/'owner_review_manifest.json');assert packet['estimated_minutes']<=120 and not packet['human_review_complete']
    assert all(c['human_reviewed_at'] is None and c['human_review_status']=='not_started' for c in packet['cases'])

def test_random_review_selection_is_reproducible_and_complete_release_grouped():
    from earnings.hybrid.review_packet import selection
    cs=read(ROOT/'diagnostic_manifest.json')['cases'];a=selection(cs);b=selection(list(reversed(cs)))
    assert a==b and len(a[0])==4 and len({x['id'] for x in a[0]+a[1]})==len(a[0]+a[1])

def sleepy_mock_worker(config,prompt,payload,output):
    time.sleep(2)
    write(output,{'status':'synthetic_worker'})

def test_parent_wall_timeout_terminates_worker_without_assuming_free(tmp_path,c):
    c['wall_timeout_seconds']=1
    result=transport.dispatch(c,'synthetic','synthetic',tmp_path/'out.json',worker=sleepy_mock_worker)
    assert result['status']=='timeout_unknown_usage' and result['usage'] is None

def reserve_worker(path,c,index,queue):
    try:queue.put(ledger.Ledger(path).reserve(str(index),c,{},STAMP))
    except ledger.Gate:queue.put(None)

def test_atomic_concurrency_across_processes(tmp_path,c):
    import multiprocessing
    path=tmp_path/'ledger';ledger.Ledger(path);ctx=multiprocessing.get_context('spawn');q=ctx.Queue()
    workers=[ctx.Process(target=reserve_worker,args=(path,c,i,q)) for i in range(5)]
    for w in workers:w.start()
    results=[q.get(timeout=20) for w in workers]
    for w in workers:w.join(20);assert w.exitcode==0
    assert sum(x is not None for x in results)==2 and ledger.Ledger(path).summary()['active_attempts']==2

def test_retry_and_cache_reuse_with_only_fake_provider(tmp_path,c,monkeypatch):
    monkeypatch.setattr(runner,'DATA',tmp_path)
    monkeypatch.setattr(runner,'preflight',lambda c:None)
    case=read(ROOT/'diagnostic_manifest.json')['cases'][0];l=ledger.Ledger(tmp_path/'l');calls=[]
    def fake(config,prompt,payload,output):
        calls.append(payload)
        if len(calls)==1:return {'status':'transport_error','http_code':429,'usage':None}
        return {'status':'response','text':'{"observations":[],"unresolved_sections":[]}','usage':{'prompt_token_count':10,'candidates_token_count':2,'thoughts_token_count':3,'total_token_count':15},'returned_model_version':'gemini-3.6-flash-test'}
    r=runner.process_case(case,c,l,send=fake,sleep=lambda n:None)
    assert len(calls)==2 and r['cache_status']=='miss' and l.summary()['attempts']==2
    assert 'gold_ids' not in calls[0] and 'review_excerpt' not in calls[0]
    r=runner.process_case(case,c,l,send=lambda *a:pytest.fail('Cached result made a call'))
    assert r['cache_status']=='hit' and not r['inference_performed'] and l.summary()['attempts']==2
    assert Decimal(l.summary()['outstanding_unknown_or_active_reservations_usd'])>0 # first429 usage unknown

def test_exhausted_transient_attempts_and_unsupported_model(tmp_path,c,monkeypatch):
    monkeypatch.setattr(runner,'DATA',tmp_path);monkeypatch.setattr(runner,'preflight',lambda c:None)
    case=read(ROOT/'diagnostic_manifest.json')['cases'][0];l=ledger.Ledger(tmp_path/'l')
    fake=lambda *a:{'status':'transport_error','http_code':503,'usage':None}
    r=runner.process_case(case,c,l,send=fake,sleep=lambda n:None)
    assert r['status']=='FAILED_RETRIES_EXHAUSTED' and l.summary()['attempts']==3
    case=read(ROOT/'diagnostic_manifest.json')['cases'][1]
    with pytest.raises(ledger.Gate,match='UNSUPPORTED_NO_SUBSTITUTION'):
        runner.process_case(case,c,l,send=lambda *a:{'status':'transport_error','http_code':404,'usage':None},sleep=lambda n:None)
    assert l.summary()['halted']

def test_prices_above_accounting_or_stale_stop_before_any_call(c):
    p={'checked_at':STAMP.isoformat(),'model':c['model'],'provider':c['provider'],'input_upper_usd_per_million':'1.50','output_including_thinking_upper_usd_per_million':'7.50'}
    runner.price_gate(c,p,STAMP)
    with pytest.raises(ledger.Gate,match='EXCEEDS'):runner.price_gate(c,{**p,'output_including_thinking_upper_usd_per_million':'7.51'},STAMP)
    with pytest.raises(ledger.Gate,match='REFRESH'):runner.price_gate(c,p,STAMP+timedelta(hours=7))

def test_calendar_can_resolve_physical_bounds_but_not_guess_missing_fiscal_label():
    data,docs=fixture();data['observations'][0].update(period_start=None,period_end=None)
    r=validate(data,docs,cal)['observations'][0]
    assert r['resolved_period_start']=='2026-05-01' and not r['deterministic_errors']
    data['observations'][0]['fiscal_year']=None
    assert 'UNRESOLVED_FISCAL_CALENDAR' in validate(data,docs,cal)['observations'][0]['deterministic_errors']

def test_no_model_results_are_not_reported_as_zero_recall(tmp_path,monkeypatch):
    from earnings.hybrid import diagnostic_score
    monkeypatch.setattr(diagnostic_score,'DATA',tmp_path)
    run=tmp_path/'run.json';write(run,{'stage':'diagnostic_only','results':[]})
    r=diagnostic_score.evaluate(run,tmp_path/'score.json')
    assert r['performance_status']=='NOT_EVALUATED_NO_MODEL_RESULTS' and r['whole_release_pilot_scope'] is None and not r['abstentions']

def test_actual_sdk_serializes_full_schema_and_separate_thinking_usage(c,monkeypatch):
    import httpx
    from google import genai
    from google.genai import types
    from google.oauth2.credentials import Credentials
    monkeypatch.delenv('GOOGLE_API_KEY',raising=False);monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    sent=[]
    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200,json={'candidates':[{'content':{'role':'model','parts':[{'text':'{"observations":[],"unresolved_sections":[]}'}]},'finishReason':'STOP'}],'modelVersion':'gemini-3.6-flash-mock','usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':10,'thoughtsTokenCount':20,'totalTokenCount':130}})
    client=genai.Client(vertexai=True,project=c['project'],location='global',credentials=Credentials(token='synthetic-test-not-a-secret'),http_options=types.HttpOptions(timeout=300000,retry_options=types.HttpRetryOptions(attempts=1),client_args={'transport':httpx.MockTransport(handler)}))
    _,config=transport.sdk_options(c)
    with client:r=client.models.generate_content(model=c['model'],contents='Synthetic local HTTP mock only',config=config)
    assert sent[0]['generationConfig']['responseMimeType']=='application/json'
    assert sent[0]['generationConfig']['responseSchema']
    assert r.usage_metadata.candidates_token_count==10 and r.usage_metadata.thoughts_token_count==20 and r.usage_metadata.total_token_count==130

def test_current_fresh_release_body_urls_are_not_in_own_sec_cache():
    import hashlib
    from earnings.sec import CACHE
    for issuer in read(ROOT/'fresh_manifest.json')['issuers']:
        for r in issuer.get('releases',[]):assert not (CACHE/(hashlib.sha256(r['primary_url'].encode()).hexdigest()+'.json')).exists()

def test_unexpected_tool_usage_halts_and_keeps_reservation(tmp_path,c):
    l=ledger.Ledger(tmp_path/'l');aid=l.reserve('x',c,{},STAMP)
    l.finish(aid,{'prompt_token_count':100,'candidates_token_count':10,'thoughts_token_count':20,'tool_use_prompt_token_count':5,'total_token_count':135})
    assert l.summary()['halted'] and l.summary()['records'][0]['accounted_nano'] is None
