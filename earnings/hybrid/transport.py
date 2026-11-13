"""Vertex single-attempt adapter. Never instantiate a client during preparation.

Only the authorized runner calls dispatch. No dotenv, credential-file inspection,
model/access probes, countTokens, batch, storage, tools or automatic continuation.
"""
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
    # Called only in a sanitized, authorized child process. Credentials omitted:
    # SDK ADC normally resolves them; no code reads or copies credential files.
    client=factory(vertexai=True,project='just-rhythm-506202-j8',location='global',api_key=None,http_options=http)
    return client,generation


def _worker(config,prompt,payload,output):
    # Explicitly discard possible shell API keys without inspecting or logging
    # values. No .env is loaded. Explicit arguments override model/project env.
    for name in ('GOOGLE_API_KEY','GEMINI_API_KEY'):
        os.environ.pop(name,None)
    try:
        client,generation=make_client(config)
        generation.system_instruction=prompt
        with client:
            response=client.models.generate_content(model='gemini-3.6-flash',contents=payload,config=generation)
        raw=response.model_dump(mode='json',exclude={'sdk_http_response'})
        try:text=response.text
        except (ValueError,AttributeError):text=None
        result={'status':'response','raw_response':raw,'text':text,'usage':response.usage_metadata.model_dump(mode='json') if response.usage_metadata else None,'returned_model_version':response.model_version,'sdk_version':version('google-genai')}
    except Exception as exc:
        # Error strings may contain requests/headers. Preserve safe class/code,
        # never dump credentials, headers or arbitrary exception text.
        code=getattr(exc,'code',None)
        result={'status':'transport_error','error_class':type(exc).__name__,'http_code':code if isinstance(code,int) else None,'usage':None,'returned_model_version':None,'sdk_version':version('google-genai')}
    result.update(provider='google_vertex_ai',requested_model='gemini-3.6-flash',project='just-rhythm-506202-j8',location='global')
    write(output,result)


def dispatch(config,prompt,payload,output,*,worker=_worker):
    path=Path(output)
    if path.exists():raise ValueError('Attempt output already exists')
    # Parent enforces a whole-attempt wall deadline including ADC/client setup;
    # HTTP timeout alone is not a whole-process wall clock bound.
    process=multiprocessing.get_context('spawn').Process(target=worker,args=(config,prompt,payload,str(path)))
    started=time.monotonic();process.start();process.join(max(0,config['wall_timeout_seconds']-(time.monotonic()-started)))
    if process.is_alive():
        process.terminate();process.join(1)
        if process.is_alive():process.kill();process.join(1)
        return {'status':'timeout_unknown_usage','usage':None,'returned_model_version':None,'http_code':None,'wall_limit_seconds':config['wall_timeout_seconds']}
    if not path.exists():return {'status':'worker_failed_unknown_usage','usage':None,'returned_model_version':None,'http_code':None}
    return json.loads(path.read_text())
