"""Response-body usage capture through supported HTTPX response hooks.

Never stores request/response headers, cookies, URLs, credentials or error text.
The body is hashed in memory; only allowlisted response metadata is persisted.
"""
import hashlib,json
COUNTERS=('promptTokenCount','candidatesTokenCount','thoughtsTokenCount',
          'totalTokenCount','cachedContentTokenCount','toolUsePromptTokenCount')

def capture_body(body,status_code):
    out={'body_sha256':hashlib.sha256(body).hexdigest(),'body_bytes':len(body),
         'status_code':status_code,'capture':'original HTTP JSON before SDK parsing; metadata allowlist only'}
    try:data=json.loads(body)
    except (ValueError,UnicodeDecodeError):return {**out,'json_valid':False}
    if not isinstance(data,dict):return {**out,'json_valid':False}
    usage=data.get('usageMetadata');out.update(json_valid=True,
        usage_metadata_present='usageMetadata' in data,
        usage_metadata_is_null='usageMetadata' in data and usage is None)
    if not isinstance(usage,dict):return out
    out['usage_fields']={}
    for name in COUNTERS:
        present=name in usage;value=usage.get(name)
        safe=value is None or type(value) is int and value>=0
        out['usage_fields'][name]={'present':present,'is_null':present and value is None,
            'value':value if present and safe else None,'type_valid':not present or safe}
    # No arbitrary nested metadata or names are logged.
    return out

class ResponseCapture:
    def __init__(self):self.responses=[]
    def __call__(self,response):
        response.read() # HTTPX response hooks run before the body is consumed.
        self.responses.append(capture_body(response.content,response.status_code))
