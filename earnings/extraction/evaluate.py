"""Gold benchmark: gold never enters extract(); no production writes."""
import argparse,json,hashlib,re
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from decimal import Decimal
from .corpus import gold,documents,materialize,ROOT,CACHE
from .rules import extract,references,VERSION
from earnings.models import dumps,record_id
FIELDS=('low','high','unit','basis','start','end','metric','issued','filed','status','accession','exhibit')


def equal(field,a,b):
    if field in ('low','high'):
        return a is None and b is None or a is not None and b is not None and Decimal(a)==Decimal(b)
    return a==b


def summarize(tp,pred,gold_count):
    return {'true_positive':tp,'predicted':pred,'gold':gold_count,'false_positive':pred-tp,'false_negative':gold_count-tp,
       'precision':str(Decimal(tp)/Decimal(pred)) if pred else None,'recall':str(Decimal(tp)/Decimal(gold_count)) if gold_count else None}


def run(split,output):
    expected=[g for g in gold()['records'] if g['split']==split];by_doc={};prior={};candidates=[];gaps=[];manifests=[];errors=[];rejections=[]
    for g in expected:by_doc.setdefault(g['source_url'],[]).append(g)
    for d in documents(split):
        try:text,meta=materialize(d)
        except (ValueError,RuntimeError,OSError) as exc:gaps.append({'source_url':d['source_url'],'code':str(exc)});continue
        manifests.append(meta);cs,rejected=extract(text,meta)
        present={(c['metric'],c['start'],c['end']) for c in cs}
        cs.extend(c for c in references(text,meta,prior) if (c['metric'],c['start'],c['end']) not in present)
        unique={}
        for c in cs:unique.setdefault((c['metric'],c['start'],c['end'],Decimal(c['low']),Decimal(c['high'])),c)
        cs=list(unique.values())
        rejections.extend({'source_url':d['source_url'],**r} for r in rejected)
        for c in cs:
            key=(c['company'],c['metric'],c['start'],c['end']);old=prior.get(key)
            if old and not c.get('carried_from_candidate_id'):
                if Decimal(c['low'])==Decimal(old['low']) and Decimal(c['high'])==Decimal(old['high']):c['status']=old['status'] if re.search(r'revised|amend',text[:3000],re.I) or re.search(r'am\.htm|revised|8-ka',meta['source_url'],re.I) else 'reaffirmed'
                elif Decimal(c['low'])>=Decimal(old['low']) and Decimal(c['high'])>=Decimal(old['high']):c['status']='raised'
                elif Decimal(c['low'])<=Decimal(old['low']) and Decimal(c['high'])<=Decimal(old['high']):c['status']='lowered'
                else:c['status']='initial';c['status_review']='Mixed-endpoint revision; no directional claim'
            prior[key]=c
            c['id']=record_id('evaluated-candidate-v1',c)
            assert text[c['quote_start']:c['quote_end']]==c['quote']
            candidates.append(c)
    # Positive-only gold does not exhaustively label other metrics in each release.
    # Scope includes ALL candidates for each document+metric represented by gold;
    # wrong target periods and extra ranges within that scope count as errors.
    scope={(g['source_url'],g['metric']) for g in expected}
    scoped=[c for c in candidates if (c['source_url'],c['metric']) in scope]
    extras=[c for c in candidates if (c['source_url'],c['metric']) not in scope]
    available=list(scoped);matched=[];field_counts=Counter();tp=0
    for g in expected:
        possible=[c for c in available if c['source_url']==g['source_url'] and c['metric']==g['metric']]
        if not possible:
            errors.append({'gold_id':g['id'],'company':g['company'],'source_url':g['source_url'],'type':'miss','expected':g});continue
        c=max(possible,key=lambda c:sum(equal(f,c.get(f),g.get(f)) for f in FIELDS));available.remove(c)
        mismatch={f:{'expected':g.get(f),'actual':c.get(f)} for f in FIELDS if not equal(f,c.get(f),g.get(f))}
        for f in FIELDS:
            if f not in mismatch:field_counts[f]+=1
        if not mismatch:tp+=1
        else:errors.append({'gold_id':g['id'],'candidate_id':c['id'],'company':g['company'],'source_url':g['source_url'],'type':'field_errors','fields':mismatch,'quote':c['quote']})
        matched.append({'gold_id':g['id'],'candidate_id':c['id'],'exact':not mismatch})
    for c in available:errors.append({'candidate_id':c['id'],'company':c['company'],'source_url':c['source_url'],'type':'unmatched_in_scope_candidate','candidate':c})
    core=('low','high','unit','basis','start','end','metric')
    numeric_tp=sum(all(equal(f,c.get(f),g.get(f)) for f in core) for g in expected for pair in matched if pair['gold_id']==g['id'] for c in scoped if c['id']==pair['candidate_id'])
    result={'executed_at':datetime.now(timezone.utc).isoformat(),'method_version':VERSION,'split':split,
      'gold_sha256':hashlib.sha256((ROOT/'gold_v1.json').read_bytes()).hexdigest(),'rules_sha256':hashlib.sha256((ROOT/'rules.py').read_bytes()).hexdigest(),
      'strict_record':summarize(tp,len(scoped),len(expected)),'value_period_metric':summarize(numeric_tp,len(scoped),len(expected)),
      'fields':{f:summarize(field_counts[f],len(scoped),len(expected)) for f in FIELDS},
      'quote_validation':{'all_candidates_have_literal_canonical_offsets':True,'gold_exact_quote_span_not_required':'Manual quotations may include multiple rows or arbitrary truncation; candidate must independently occur verbatim at saved offsets.'},
      'scope':'Document+metric cells represented in fixed positive gold; wrong periods/ranges in those cells count as errors. Other document+metric candidates are unjudged, never assumed correct.',
      'unjudged_out_of_scope_count':len(extras),'all_candidate_count':len(candidates),'errors':errors,'source_gaps':gaps,'rejected':rejections,'matches':matched,'sources':manifests,
      'limitations':gold()['limitations']+['Issuer calendar and unqualified consolidated reported revenue basis use documented manual metadata, not textual extraction of those conventions. Metadata accession/exhibit/filing is supplied by SEC corpus inventory.',
      'In-scope unmatched outputs counted conservatively as false positives; positive-only gold does not measure open-world precision. No company-universe expansion or automatic production adoption.']}
    out=Path(output);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as stream:stream.write(dumps(result)+'\n')
    with out.with_suffix('.candidates.json').open('x') as stream:stream.write(dumps({'research_only':True,'split':split,'candidates':candidates,'unjudged_ids':[c['id'] for c in extras]})+'\n')
    print(dumps({k:result[k] for k in ['split','strict_record','value_period_metric','unjudged_out_of_scope_count','all_candidate_count']}))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--split',required=True,choices=['development','heldout']);p.add_argument('--output',required=True);a=p.parse_args();run(a.split,a.output)
