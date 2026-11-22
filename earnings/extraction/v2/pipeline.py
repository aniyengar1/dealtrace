"""Source-only candidate history. Partials are not accepted predictions/guidance."""
from decimal import Decimal
from .rules import extract,references,assign_status
from earnings.models import record_id


def process(body,metadata,prior):
    text,obs,blocked=extract(body,metadata);refs,rb=references(body,metadata,prior);blocked.extend(rb)
    emitted=[];partials=[];seen={}
    for c in obs+refs:
        key=(c['company'],c['metric'],c['start'],c['end'])
        identity=(key,c['low'] is None,Decimal(c['low']) if c['low'] is not None else None,Decimal(c['high']) if c['high'] is not None else None)
        if identity in seen:continue
        seen[identity]=c
        if c['origin']!='explicit_reference':
            old=prior.get(key)
            if old and old['status']=='withdrawn':c['status']=None;reason='WITHDRAWN_REFERENCE_REQUIRES_REINSTATEMENT'
            else:c['status'],reason=assign_status(c,prior,{**metadata,'document_text':text})
            c['status_reason']=reason
        c['id']=record_id('v2-research-candidate',c)
        if not c['status']:
            partials.append(c);blocked.append({'code':c['status_reason'],'partial_id':c['id'],'metric':c['metric'],'start':c['start'],'end':c['end'],'quote':c['quote'],'source_url':c['source_url']})
        else:emitted.append(c)
        # Numeric evidence can support a later comparison even if this record's
        # initial/revision status is unresolved. It never becomes production.
        prior[key]=c
    return text,emitted,partials,blocked
