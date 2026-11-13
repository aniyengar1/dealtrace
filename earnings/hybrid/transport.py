"""Single-attempt Vertex transport. ADC through SDK only; no API-key defaults."""
import json,multiprocessing,os,time
from pathlib import Path
from importlib.metadata import version
from .prepare import write


def sdk_options(config):
    from google.genai import types
    from .schema import Extraction
    http=types.HttpOptions(api_version='v1',base_url='https://aiplatform.googleapis.com',timeout=config['http_timeout_ms'],retry_options=types.HttpRetryOptions(attempts=1))
    generation=types.GenerateContentConfig(temperature=0,candidate_count=1,max_output_tokens=config['max_output_tokens'],response_schema=Extraction,response_mime_type='application/json',thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW,include_thoughts=False),automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),automatic_continuation=False)
    return http,generation


def make_client(config,factory=None):
    if version('google-genai')!='2.34.0':raise ValueError('Pinned SDK mismatch')
    http,generation=sdk_options(config)
    if factory is None:
        from google import genai
        factory=genai.Client
    return factory(vertexai=True,project='just-rhythm-506202-j8',location='global',api_key=None,http_options=http),generation


def _worker(config,prompt,payload,output):
    for name in ('GOOGLE_API_KEY','GEMINI_API_KEY'):os.environ.pop(name,None)
    started=time.monotonic();operation=config.get('_operation','generate')
    try:
        from google.genai import types,_transformers
        from .schema import Extraction
        client,generation=make_client(config);generation.system_instruction=prompt
        with client:
            if operation=='count':
                # Count same content/instructions/settings. Explicitly supplement
                # schema/settings as text because config schema token inclusion
                # is not uniformly documented. Conservative, not exact billing.
                schema=_transformers.t_schema(None,Extraction)
                cg=types.GenerationConfig(response_schema=schema,response_mime_type='application/json',max_output_tokens=config['max_output_tokens'],thinking_config=types.ThinkingConfig(thinking_level='LOW'),temperature=0)
                supplement=json.dumps({'response_schema':Extraction.model_json_schema(),'max_output_tokens':config['max_output_tokens'],'thinking_level':'LOW','response_mime_type':'application/json'},sort_keys=True)
                r=client.models.count_tokens(model='gemini-3.6-flash',contents=[payload,'COUNTING-ONLY SCHEMA/SETTINGS SUPPLEMENT: '+supplement],config=types.CountTokensConfig(system_instruction=prompt,generation_config=cg))
                result={'status':'count_response','counted_input_tokens':r.total_tokens,'raw_response':r.model_dump(mode='json',exclude={'sdk_http_response'}),'accounted_counting_cost_usd':'0','count_scope':'full contents/system/generation config plus explicit schema/settings text supplement; may conservatively double-count schema; not exact billable input','usage':None,'returned_model_version':None}
            else:
                r=client.models.generate_content(model='gemini-3.6-flash',contents=payload,config=generation)
                try:text=r.text
                except (ValueError,AttributeError):text=None
                result={'status':'response','raw_response':r.model_dump(mode='json',exclude={'sdk_http_response'}),'text':text,'usage':r.usage_metadata.model_dump(mode='json') if r.usage_metadata else None,'returned_model_version':r.model_version,'finish_reasons':[str(x.finish_reason.value if hasattr(x.finish_reason,'value') else x.finish_reason) for x in r.candidates or []]}
    except Exception as exc:
        code=getattr(exc,'code',None)
        result={'status':'transport_error','error_class':type(exc).__name__,'http_code':code if isinstance(code,int) else None,'usage':None,'returned_model_version':None}
    result.update(provider='google_vertex_ai',requested_model='gemini-3.6-flash',project='just-rhythm-506202-j8',location='global',operation=operation,sdk_version=version('google-genai'),latency_seconds=str(time.monotonic()-started))
    write(output,result)


def dispatch(config,prompt,payload,output,*,worker=_worker):
    path=Path(output)
    if path.exists():raise ValueError('Attempt output already exists')
    process=multiprocessing.get_context('spawn').Process(target=worker,args=(config,prompt,payload,str(path)))
    started=time.monotonic();process.start();process.join(max(0,config['wall_timeout_seconds']-(time.monotonic()-started)))
    if process.is_alive():
        process.terminate();process.join(1)
        if process.is_alive():process.kill();process.join(1)
        return {'status':'timeout_unknown_usage','usage':None,'returned_model_version':None,'http_code':None,'wall_limit_seconds':config['wall_timeout_seconds'],'latency_seconds':str(time.monotonic()-started)}
    if not path.exists():return {'status':'worker_failed_unknown_usage','usage':None,'returned_model_version':None,'http_code':None}
    return json.loads(path.read_text())
