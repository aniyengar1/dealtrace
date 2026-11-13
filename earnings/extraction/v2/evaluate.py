"""V2 separate benchmark; original v1 snapshots, rules and outputs stay unchanged."""
import argparse,hashlib,json
from datetime import datetime,timezone
from collections import Counter
from decimal import Decimal
from pathlib import Path
from earnings.models import dumps
from earnings.extraction.corpus import gold,documents
from earnings.extraction.evaluate import FIELDS,equal,summarize
from .corpus import materialize,ROOT
from .pipeline import process
from .rules import VERSION


def score(expected,candidates,scope_all=False):
    scope={(g['source_url'],g['metric']) for g in expected}
    scoped=candidates if scope_all else [c for c in candidates if (c['source_url'],c['metric']) in scope]
    available=list(scoped);errors=[];matches=[];counts=Counter();tp=0
    for g in expected:
        choices=[c for c in available if c['source_url']==g['source_url'] and c['metric']==g['metric']]
        if not choices:errors.append({'type':'miss','gold_id':g['id'],'company':g['company'],'expected':g});continue
        c=max(choices,key=lambda c:sum(equal(f,c.get(f),g.get(f)) for f in FIELDS));available.remove(c)
        diff={f:{'expected':g.get(f),'actual':c.get(f)} for f in FIELDS if not equal(f,c.get(f),g.get(f))}
        for f in FIELDS:
            if f not in diff:counts[f]+=1
        if not diff:tp+=1
        else:errors.append({'type':'field_errors','gold_id':g['id'],'candidate_id':c['id'],'company':g['company'],'fields':diff,'quote':c['quote']})
        matches.append({'gold_id':g['id'],'candidate_id':c['id'],'exact':not diff})
    for c in available:errors.append({'type':'unmatched_candidate','candidate_id':c['id'],'company':c['company'],'candidate':c})
    return {'strict_record':summarize(tp,len(scoped),len(expected)),'fields':{f:summarize(counts[f],len(scoped),len(expected)) for f in FIELDS},'errors':errors,'matches':matches,
       'unjudged_count':len(candidates)-len(scoped)}


def run(dataset,output):
    if dataset in ['development','old-heldout-diagnostic']:
        split='development' if dataset=='development' else 'heldout';expected=[g for g in gold()['records'] if g['split']==split];docs=documents(split);context=[]
    else:
        fresh=json.loads((ROOT/'fresh_gold.json').read_text());expected=fresh['records'];docs=fresh['evaluation_documents'];context=fresh['context_documents']
    prior={};candidates=[];partials=[];abstentions=[];sources=[];gaps=[]
    context_urls={d['source_url'] for d in context}
    for d in sorted(context+docs,key=lambda d:(d['filed'],d['company'],d['source_url'])):
        try:body,meta=materialize(d)
        except (ValueError,RuntimeError,OSError) as exc:gaps.append({'company':d['company'],'source_url':d['source_url'],'code':type(exc).__name__});continue
        text,cs,ps,blocked=process(body,meta,prior)
        for c in cs+ps:
            if text[c['quote_start']:c['quote_end']]!=c['quote']:raise ValueError('Quote offset mismatch')
        if d['source_url'] not in context_urls:candidates.extend(cs);partials.extend(ps);abstentions.extend(blocked)
        sources.append({k:v for k,v in meta.items() if k!='primary_text'})
    result={'dataset':dataset,'executed_at':datetime.now(timezone.utc).isoformat(),'method_version':VERSION,
       'score_scope':'All records in exhaustively reviewed fresh documents' if dataset=='fresh' else 'Original fixed gold document+metric scope; all old holdout examples now diagnostic, not fresh',
       **score(expected,candidates,dataset=='fresh'),'per_company':{t:score([g for g in expected if g['company']==t],[c for c in candidates if c['company']==t],dataset=='fresh')['strict_record'] for t in sorted({g['company'] for g in expected})},
       'candidates':candidates,'partials':partials,'abstentions':abstentions,'abstention_counts':dict(Counter(b['code'] for b in abstentions)),
       'source_gaps':gaps,'sources':sources,'gold_count':len(expected),'rules_sha256':hashlib.sha256((ROOT/'rules.py').read_bytes()).hexdigest()}
    with Path(output).open('x') as stream:stream.write(dumps(result)+'\n')
    print(dumps({'dataset':dataset,'strict_record':result['strict_record'],'abstention_counts':result['abstention_counts']}));return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',choices=['development','old-heldout-diagnostic','fresh'],required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.dataset,a.output)
