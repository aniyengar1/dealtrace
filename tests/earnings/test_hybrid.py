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
    # Mock-only safety tests must not expire with the real experiment deadline.
    # Production clocks, the paused experiment and its November17 deadline stay
    # unchanged. Explicit deadline-boundary fixtures still pass their own clock.
    class TestClock(datetime):
        @classmethod
        def now(cls,tz=None):
            fixed=datetime(2026,11,16,12,tzinfo=timezone.utc)
            return fixed.astimezone(tz) if tz else fixed.replace(tzinfo=None)
    monkeypatch.setattr(ledger,'now',lambda:datetime(2026,11,16,12,tzinfo=timezone.utc))
    monkeypatch.setattr(runner,'datetime',TestClock)

@pytest.fixture
def c():
    result=runner.configuration();result.update(reservation_policy='verified_bound_legacy_for_mock',billable_thinking_bound_verified=True,max_input_tokens_documented=10000,max_billable_output_tokens=8192,max_attempts_per_item=3)
    return result # synthetic verified bounds for tests only; real config false

STAMP=datetime(2026,11,13,12,tzinfo=timezone.utc)

def test_real_configuration_blocks_unverified_bounds_without_charge(tmp_path):
    l=ledger.Ledger(tmp_path/'ledger.sqlite');real=runner.configuration()
    with pytest.raises(ledger.Gate,match='PROVIDER_INPUT_COUNT_REQUIRED'):l.reserve('x',real,{},STAMP)
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
    c.update(max_input_tokens_documented=600000,max_billable_output_tokens=600000)
    l=ledger.Ledger(tmp_path/'l');aid=l.reserve('x',c,{},STAMP);l.finish(aid,None,state='timeout')
    assert l.summary()['total_held_usd']=='5.4'
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

def test_preflight_never_constructs_client_without_authorization(monkeypatch,tmp_path):
    monkeypatch.setattr(runner,'check_prompt_freeze',lambda c:None)
    monkeypatch.setattr(transport,'make_client',lambda *a,**k:pytest.fail('Client constructed'))
    config=runner.configuration();monkeypatch.setattr(runner,'ROOT',tmp_path)
    with pytest.raises(ledger.Gate,match='NO_EXPLICIT_INFERENCE_AUTHORIZATION'):runner.preflight(config,STAMP)

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
    roles=['metric','scope','period','units','basis','guidance_type','amount','issuance','status']
    obs={'source_id':'current','metric_label':'revenue','metric_class':'consolidated_revenue','scope':'consolidated','scope_support':'explicit','basis_kind':'reported','scope_qualifiers':[],'fiscal_year':2026,'fiscal_quarter':3,'period_start':'2026-05-01','period_end':'2026-07-31','issued_start':'2026-05-20','issued_end':'2026-05-20','issued_precision':'day','currency':'USD','guidance_type':'direct','amount_style':'absolute_tolerance','low':None,'high':None,'center':{'value':'2.40','scale':'1000000000'},'tolerance':{'value':'100','scale':'1000000'},'status':'initial','status_support':'explicit_issuance','prior_observation_index':None,'table_id':None,'column_label':None,'table_row_index':None,'table_column_index':None,'evidence':[{'source_id':'current','start':0,'end':len(text),'quote':text,'role':r} for r in roles],'review_note':'synthetic, not real guidance'}
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
    assert 'MISSING_EXACT_MATCH' in validate(d,docs,cal)['observations'][0]['deterministic_errors']
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

def fake_count(*args):return {'status':'count_response','counted_input_tokens':1234,'accounted_counting_cost_usd':'0'}

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
        if len(calls)==1:return {'status':'transport_error','http_code':503,'usage':None} # legacy transient-only retry fixture; quota must stop
        return {'status':'response','text':'{"observations":[],"unresolved_sections":[]}','usage':{'prompt_token_count':10,'candidates_token_count':2,'thoughts_token_count':3,'total_token_count':15},'returned_model_version':'gemini-3.6-flash-test'}
    r=runner.process_case(case,c,l,send=fake,count_send=fake_count,sleep=lambda n:None)
    assert len(calls)==2 and r['cache_status']=='miss' and l.summary()['attempts']==2
    assert 'gold_ids' not in calls[0] and 'review_excerpt' not in calls[0]
    r=runner.process_case(case,c,l,send=lambda *a:pytest.fail('Cached result made a call'),count_send=lambda *a:pytest.fail('Cached result recounted'))
    assert r['cache_status']=='hit' and not r['inference_performed'] and l.summary()['attempts']==2
    assert Decimal(l.summary()['outstanding_unknown_or_active_reservations_usd'])>0 # first429 usage unknown

def test_exhausted_transient_attempts_and_unsupported_model(tmp_path,c,monkeypatch):
    monkeypatch.setattr(runner,'DATA',tmp_path);monkeypatch.setattr(runner,'preflight',lambda c:None)
    case=read(ROOT/'diagnostic_manifest.json')['cases'][0];l=ledger.Ledger(tmp_path/'l')
    fake=lambda *a:{'status':'transport_error','http_code':503,'usage':None}
    r=runner.process_case(case,c,l,send=fake,count_send=fake_count,sleep=lambda n:None)
    assert r['status']=='FAILED_RETRIES_EXHAUSTED' and l.summary()['attempts']==3
    case=read(ROOT/'diagnostic_manifest.json')['cases'][1]
    with pytest.raises(ledger.Gate,match='UNSUPPORTED_NO_SUBSTITUTION'):
        runner.process_case(case,c,l,send=lambda *a:{'status':'transport_error','http_code':404,'usage':None},count_send=fake_count,sleep=lambda n:None)
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

def test_original_owner_estimate_preserved_for_existing_reservation(tmp_path):
    c=read(ROOT/'archive/probe_v2/config.json');l=ledger.Ledger(tmp_path/'l')
    aid=l.reserve('x',c,{'counted_input_tokens':1000,'is_probe':True},STAMP)
    row=l.summary()['records'][0]
    assert row['reserved_nano']>=1_000_000_000
    assert row['reserved_nano']>=ledger.cost(1000+1024,2*65536)
    l.finish(aid,None,state='timeout')
    assert l.summary()['total_held_usd']==ledger.usd(row['reserved_nano'])
    with pytest.raises(ledger.Gate,match='EXHAUSTED'):l.reserve('x',c,{'counted_input_tokens':1000,'is_probe':True},STAMP)

def test_probe_gate_usage_cost_model_and_finish():
    r={'result':{'status':'response','accounted_nano':500_000_000,'returned_model_version':'gemini-3.6-flash','finish_reasons':['STOP'],'validation':{'observations':[]}}}
    runner.probe_gate(r)
    for field,value in [('accounted_nano',500_000_001),('accounted_nano',None),('returned_model_version','different-model'),('finish_reasons',['MAX_TOKENS'])]:
        bad=deepcopy(r);bad['result'][field]=value
        with pytest.raises(ledger.Gate):runner.probe_gate(bad)

def test_probe_transport_failure_has_one_attempt_no_retry(tmp_path,c,monkeypatch):
    monkeypatch.setattr(runner,'DATA',tmp_path);monkeypatch.setattr(runner,'preflight',lambda c:None)
    case=read(ROOT/'diagnostic_manifest.json')['cases'][0];l=ledger.Ledger(tmp_path/'l');calls=[]
    def fake(*args):calls.append(1);return {'status':'transport_error','http_code':503,'usage':None}
    with pytest.raises(ledger.Gate,match='PROBE_FAILED_NO_RETRIES'):runner.process_case(case,c,l,send=fake,count_send=fake_count,is_probe=True)
    assert len(calls)==1 and l.summary()['attempts']==1

def test_usage_over_fifty_cents_is_accounted_true_and_halts(tmp_path):
    c=runner.configuration();l=ledger.Ledger(tmp_path/'l');aid=l.reserve('x',c,{'counted_input_tokens':5000},STAMP)
    usage={'prompt_token_count':5000,'candidates_token_count':1000,'thoughts_token_count':66000,'total_token_count':72000}
    l.finish(aid,usage)
    assert l.summary()['records'][0]['accounted_nano']==ledger.cost(5000,67000)
    assert l.summary()['halted']

def test_sdk_count_request_includes_instructions_schema_and_supplement(c,monkeypatch):
    import httpx
    from google import genai
    from google.genai import types,_transformers
    from google.oauth2.credentials import Credentials
    from earnings.hybrid.schema import Extraction
    monkeypatch.delenv('GOOGLE_API_KEY',raising=False);monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    sent=[]
    def handler(request):sent.append(json.loads(request.content));return httpx.Response(200,json={'totalTokens':1234})
    client=genai.Client(vertexai=True,project=c['project'],location='global',credentials=Credentials(token='synthetic-test-not-a-secret'),http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1),client_args={'transport':httpx.MockTransport(handler)}))
    cfg=types.CountTokensConfig(system_instruction='instruction',generation_config=types.GenerationConfig(response_schema=_transformers.t_schema(None,Extraction),response_mime_type='application/json'))
    with client:r=client.models.count_tokens(model=c['model'],contents=['payload','SCHEMA '+json.dumps(Extraction.model_json_schema())],config=cfg)
    assert r.total_tokens==1234 and sent[0]['generationConfig']['responseSchema'] and sent[0]['systemInstruction']
    assert 'SCHEMA' in json.dumps(sent[0]['contents'])

def test_original_missing_thinking_counter_preserves_full_reservation(tmp_path):
    c=read(ROOT/'archive/probe_v2/config.json');l=ledger.Ledger(tmp_path/'l')
    aid=l.reserve('probe',c,{'counted_input_tokens':89940,'is_probe':True,'prompt_version':c['prompt_version']},STAMP)
    usage={'prompt_token_count':89449,'candidates_token_count':1901,
           'thoughts_token_count':None,'total_token_count':91350}
    l.finish(aid,usage)
    row=l.summary()['records'][0]
    assert row['accounted_nano'] is None and row['thinking_tokens'] is None
    assert row['held_nano']==row['reserved_nano']==1_120_000_000
    assert runner.dispatch_status(c,l)=='PROBE_USAGE_UNRESOLVED_STOP_REVIEW_REQUIRED'
    with pytest.raises(ledger.Gate,match='USAGE_OR_RESPONSE'):
        runner.probe_gate({'result':{'status':'response','accounted_nano':None}})

def test_unique_quote_location_preserves_wrong_model_offsets_and_multiple_roles():
    d,docs=fixture();o=d['observations'][0]
    span=deepcopy(o['evidence'][0]);span.update(start=99,end=100,roles=[e['role'] for e in o['evidence']]);span.pop('role');o['evidence']=[span]
    before=deepcopy(d);r=validate(d,docs,cal)['observations'][0]
    assert not r['deterministic_errors'] and d==before
    assert r['evidence_locations'][0]['original']['start']==99
    assert r['evidence_locations'][0]['resolved']=={'start':0,'end':len(docs[0]['canonical_text'])}
    assert r['evidence_locations'][0]['semantic_validation']=='NOT_GUARANTEED'

def test_duplicate_exact_quote_blocks_even_if_model_offset_matches():
    d,docs=fixture();docs[0]['canonical_text']+=' '+docs[0]['canonical_text']
    r=validate(d,docs,cal)['observations'][0]
    assert 'REPEATED_EXACT_MATCH' in r['deterministic_errors']
    assert r['evidence_locations'][0]['original_offsets_match']
    assert r['evidence_locations'][0]['resolved'] is None

def test_missing_status_evidence_and_first_observed_are_unresolved():
    d,docs=fixture();o=d['observations'][0]
    o['evidence']=[e for e in o['evidence'] if e['role']!='status']
    o['status_support']='first_observed_quarter'
    r=validate(d,docs,cal)['observations'][0]
    assert {'MISSING_STATUS_EVIDENCE','INITIAL_NOT_ESTABLISHED'}<=set(r['deterministic_errors'])
    assert r['resolved_status']=='unresolved'

def test_none_boundaries_do_not_allow_revision_across_fiscal_targets():
    d,docs=fixture();o=d['observations'][0];prior=deepcopy(o)
    o.update(period_start=None,period_end=None,status='reaffirmed',status_support='prior_range',prior_observation_index=1)
    prior.update(source_id='prior',fiscal_quarter=2,period_start=None,period_end=None)
    docs.append({**docs[0],'source_id':'prior','filed':'2026-05-19'})
    d['observations'].append(prior)
    assert 'INCOMPARABLE_STATUS_REFERENCE' in validate(d,docs,cal)['observations'][0]['deterministic_errors']

@pytest.mark.parametrize('counter,attribute',[('promptTokenCount','prompt_token_count'),('candidatesTokenCount','candidates_token_count'),('thoughtsTokenCount','thoughts_token_count'),('totalTokenCount','total_token_count'),('cachedContentTokenCount','cached_content_token_count'),('toolUsePromptTokenCount','tool_use_prompt_token_count')])
@pytest.mark.parametrize('kind,value',[('absent',None),('null',None),('zero',0),('numeric',37)])
def test_original_wire_usage_presence_through_supported_sdk_http_hook(c,monkeypatch,kind,value,counter,attribute):
    import httpx
    from google import genai
    from google.genai import types
    from google.oauth2.credentials import Credentials
    from earnings.hybrid.wire import ResponseCapture
    monkeypatch.delenv('GOOGLE_API_KEY',raising=False);monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    usage={'promptTokenCount':100,'candidatesTokenCount':10,'totalTokenCount':110+(value or 0)}
    usage.pop(counter,None)
    if kind!='absent':usage[counter]=value
    body={'usageMetadata':usage,'modelVersion':'gemini-3.6-flash','authorization':'DO_NOT_LOG','candidates':[{'content':{'parts':[{'text':'{}'}]},'finishReason':'STOP'}]}
    capture=ResponseCapture();http,_=transport.sdk_options(c,capture)
    http.client_args['transport']=httpx.MockTransport(lambda req:httpx.Response(200,json=body,headers={'Authorization':'DO_NOT_LOG','set-cookie':'DO_NOT_LOG'}))
    with genai.Client(vertexai=True,project=c['project'],location='global',credentials=Credentials(token='synthetic-test'),http_options=http) as client:
        r=client.models.generate_content(model=c['model'],contents='synthetic',config=types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)))
    f=capture.responses[0]['usage_fields'][counter]
    assert f['present']==(kind!='absent') and f['is_null']==(kind=='null') and f['value']==value
    assert getattr(r.usage_metadata,attribute)==value
    assert 'DO_NOT_LOG' not in json.dumps(capture.responses)

def test_offline_correction_authorization_blocks_before_provider_count(monkeypatch):
    c={**runner.configuration(),'live_authorization':'OFFLINE_CORRECTION_ONLY_NO_NEW_INFERENCE'};monkeypatch.setattr(runner,'check_prompt_freeze',lambda c:None)
    with pytest.raises(ledger.Gate,match='OFFLINE_CORRECTION_NO_NEW_INFERENCE'):runner.preflight(c)

def test_compact_proposal_preserves_all_source_and_table_content():
    from earnings.hybrid.offline_review import compact_document
    from earnings.hybrid.prepare import DATA
    if not (DATA/'pilot-0-input.json').is_file():
        pytest.skip('Optional gitignored Agilent diagnostic input unavailable; no inference fallback')
    doc=read(DATA/'pilot-0-input.json')['documents'][0];small=compact_document(doc)
    assert small['canonical_text']==doc['canonical_text'] and small['source_sha256']==doc['source_sha256']
    for old,new in zip(doc['tables'],small['tables'],strict=True):
        assert new['rows']==[[c['text'] for c in row] for row in old['rows']]
        assert (new['start'],new['end'])==(old['start'],old['end'])
        assert new['header_cells']==[[i,j] for i,row in enumerate(old['rows']) for j,c in enumerate(row) if c['tag']=='th']
    assert len(json.dumps(small))<len(json.dumps(doc))

def test_revised_reservation_exact_formula_one_attempt_and_unknown_no_double_count(tmp_path):
    c=runner.configuration();l=ledger.Ledger(tmp_path/'l')
    a=l.reserve('new',c,{'counted_input_tokens':1000},STAMP)
    assert l.summary()['records'][0]['reserved_nano']==ledger.cost(1000,8192*2)
    l.finish(a,{'prompt_token_count':900,'candidates_token_count':100,'thoughts_token_count':None,'total_token_count':1000})
    s=l.summary();assert s['known_accounted_usd']=='0' and s['total_held_usd']==ledger.usd(ledger.cost(1000,16384))
    assert s['known_counter_subtotals_usd_not_extra_charges']==ledger.usd(ledger.cost(900,100))
    with pytest.raises(ledger.Gate,match='RETRIES_EXHAUSTED'):l.reserve('new',c,{'counted_input_tokens':1000},STAMP)

def test_known_subtotal_over_reservation_halts_even_without_thinking(tmp_path):
    c=runner.configuration();l=ledger.Ledger(tmp_path/'l');a=l.reserve('new',c,{'counted_input_tokens':1000},STAMP)
    l.finish(a,{'prompt_token_count':1000,'candidates_token_count':20000,'thoughts_token_count':None})
    assert l.summary()['halted'] and l.summary()['records'][0]['held_nano']==ledger.cost(1000,20000)
    assert l.summary()['records'][0]['accounted_nano'] is None

def test_revised_diagnostic_gate_allows_quarantined_missing_usage_not_acceptance():
    r={'result':{'status':'response','returned_model_version':'gemini-3.6-flash','accounted_nano':None,'validation':{'observations':[{'quarantined':True,'review_status':'human_review_pending','evidence_locations':[],'deterministic_errors':['MISSING_EXACT_MATCH']}]}}}
    runner.diagnostic_gate(r)
    r['result']['validation']['observations'][0]['quarantined']=False
    with pytest.raises(ledger.Gate,match='QUARANTINE'):runner.diagnostic_gate(r)

def test_revised_single_attempt_transport_failure_no_retry(tmp_path,monkeypatch):
    c=runner.configuration();monkeypatch.setattr(runner,'DATA',tmp_path);monkeypatch.setattr(runner,'preflight',lambda c:None)
    l=ledger.Ledger(tmp_path/'l');calls=[]
    def fake(*args):calls.append(1);return {'status':'transport_error','http_code':503,'usage':None}
    case=read(ROOT/'diagnostic_manifest.json')['cases'][1]
    r=runner.process_case(case,c,l,send=fake,count_send=fake_count,sleep=lambda n:pytest.fail('No retry allowed'))
    assert r['status']=='FAILED_SINGLE_ATTEMPT' and len(calls)==1 and l.summary()['attempts']==1

def test_revised_missing_thinking_still_evaluates_quarantined_response(tmp_path,monkeypatch):
    c=runner.configuration();monkeypatch.setattr(runner,'DATA',tmp_path);monkeypatch.setattr(runner,'preflight',lambda c:None)
    l=ledger.Ledger(tmp_path/'l');case=read(ROOT/'diagnostic_manifest.json')['cases'][0]
    def fake(*args):return {'status':'response','returned_model_version':c['model'],'usage':{'prompt_token_count':1000,'candidates_token_count':100,'thoughts_token_count':None,'total_token_count':1100},'text':'{"observations":[],"unresolved_sections":[]}','finish_reasons':['STOP']}
    item=runner.process_case(case,c,l,send=fake,count_send=fake_count,is_probe=True)
    runner.diagnostic_gate(item)
    assert item['result']['accounted_nano'] is None and item['result']['validation']['observations']==[]
    assert l.summary()['records'][0]['held_nano']==ledger.cost(1234,16384)

def test_flagged_diagnostic_is_never_counted_as_accepted():
    from earnings.hybrid.batch_review import disposition
    r={'deterministic_errors':[],'review_flags':['SEMANTIC_HUMAN_REVIEW_REQUIRED'],'review_status':'human_review_pending'}
    assert disposition(r)=='flagged'
    r['deterministic_errors']=['UNRESOLVED_STATUS'];assert disposition(r)=='rejected'
    with pytest.raises(ValueError):disposition({'deterministic_errors':[],'review_flags':[],'review_status':'human_review_approved'})

def test_lowered_eight_dollar_budget_and_owner_pause_no_calls(tmp_path,monkeypatch):
    c=runner.configuration();assert c['ceiling_usd']=='8.00' and ledger.CEILING==8_000_000_000
    monkeypatch.setattr(transport,'dispatch',lambda *a:pytest.fail('No provider calls authorized'))
    monkeypatch.setattr(runner,'check_prompt_freeze',lambda c:None)
    with pytest.raises(ledger.Gate,match='INFERENCE_PAUSED_OWNER_REVIEW'):runner.preflight(c)

def test_eight_dollar_guard_includes_unresolved_reservations(tmp_path,c):
    c.update(max_input_tokens_documented=600000,max_billable_output_tokens=600000)
    l=ledger.Ledger(tmp_path/'l');a=l.reserve('a',c,{},STAMP);l.finish(a,None)
    assert l.summary()['ceiling_usd']=='8' and l.summary()['total_held_usd']=='5.4'
    with pytest.raises(ledger.Gate,match='BUDGET_LIMIT'):l.reserve('b',c,{},STAMP)
    assert l.summary()['records'][0]['held_nano']==5_400_000_000

@pytest.mark.parametrize('code,message',[(402,''),(403,''),(429,''),(400,'Free trial credit exhausted'),(400,'Billing disabled')])
def test_billing_and_quota_classification_without_logging_message(code,message):
    assert transport.dispatch_stop_reason(code,message)=='BILLING_CREDIT_QUOTA_OR_ACCESS_ERROR'

def test_quota_error_stops_single_attempt_and_future_dispatch(tmp_path,monkeypatch):
    c=runner.configuration();monkeypatch.setattr(runner,'DATA',tmp_path);monkeypatch.setattr(runner,'preflight',lambda c:None)
    l=ledger.Ledger(tmp_path/'l');case=read(ROOT/'diagnostic_manifest.json')['cases'][0];calls=[]
    def fake(*args):calls.append(1);return {'status':'transport_error','http_code':429,'usage':None}
    with pytest.raises(ledger.Gate,match='NO_RETRY'):runner.process_case(case,c,l,send=fake,count_send=fake_count,is_probe=True)
    assert len(calls)==1 and l.summary()['halted'] and l.summary()['records'][0]['held_nano']>0

def test_quota_count_failure_halts_before_generation_without_retry(tmp_path,monkeypatch):
    c=runner.configuration();monkeypatch.setattr(runner,'DATA',tmp_path);monkeypatch.setattr(runner,'preflight',lambda c:None)
    l=ledger.Ledger(tmp_path/'l');case=read(ROOT/'diagnostic_manifest.json')['cases'][0]
    with pytest.raises(ledger.Gate,match='NO_RETRY'):
        runner.process_case(case,c,l,count_send=lambda *a:{'status':'transport_error','http_code':429},send=lambda *a:pytest.fail('Generation forbidden after quota error'))
    assert l.summary()['halted'] and l.summary()['attempts']==0
