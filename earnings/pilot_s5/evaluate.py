"""Run frozen v2 once gold is sealed. Outputs are quarantined research only."""
import argparse,copy,hashlib,json
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from earnings.models import dumps
from earnings.extraction.corpus import canonical
from earnings.extraction.v2.pipeline import process
from earnings.extraction.v2.evaluate import score
from .collect import ROOT,CACHE_ROOT,read,write
from .review import raw
from .calendar import registration,adapter


def interval(hits,total):
    if total==0:return None
    n=Decimal(total);p=Decimal(hits)/n;z=Decimal('1.96');den=1+z*z/n
    center=(p+z*z/(2*n))/den;half=z*(p*(1-p)/n+z*z/(4*n*n)).sqrt()/den
    return {'low':str(max(Decimal(0),center-half)),'high':str(min(Decimal(1),center+half)),'method':'Wilson 95%, descriptive independent-record approximation; issuer clustering and unequal inclusion not corrected'}

def verify_freeze():
    root=ROOT.parent/'extraction'/'v2';frozen=read(root/'rules_frozen_v2.json')
    for name,digest in frozen['files'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen v2 changed: '+name)
    return frozen

def run(output):
    verify_freeze();gold=read(ROOT/'gold.json');seal=read(ROOT/'gold_seal.json')
    if hashlib.sha256((ROOT/'gold.json').read_bytes()).hexdigest()!=seal['gold_sha256']:raise ValueError('Gold not sealed')
    inv=read(ROOT/'inventory.json');sample=read(ROOT/'sample.json');cs=read(ROOT/'companies.json')['companies'];registrations=[];bycompany={};sources=[]
    for c in cs:
        collected=read(CACHE_ROOT/(c['ticker']+'-collection.json'));bycompany[c['ticker']]=collected
        registrations.append(registration(c,collected['companyfacts'],read(ROOT/'plan.json')['cutoff']))
    write(ROOT/'calendars.json',{'version':'pilot-exact-fact-calendar-v1','registrations':registrations})
    wanted={g['guidance_source_url'] for g in sample['groups']};all_candidates=[];all_partials=[];all_blocks=[];gaps=[]
    with adapter(registrations):
        prior={}
        for c in cs:
            for release in sorted(bycompany[c['ticker']]['releases'],key=lambda r:(r['filed'],r['accession'])):
                for e in release['exhibits']:
                    meta={'company':c['ticker'],'source_url':e['source_url'],'accession':release['accession'],'exhibit':'99.1','filed':release['filed'],'raw_sha256':e['manifest']['sha256'],'primary_text':canonical(raw(release['primary_manifest']))}
                    safe_prior=copy.deepcopy(prior)
                    try:text,candidates,partials,blocks=process(raw(e['manifest']),meta,safe_prior)
                    except (ValueError,KeyError) as exc:
                        gaps.append({'company':c['ticker'],'source_url':e['source_url'],'code':'CALENDAR_OR_SOURCE_RESOLUTION_FAILED','detail':str(exc)});continue
                    prior=safe_prior
                    for candidate in candidates+partials:
                        if text[candidate['quote_start']:candidate['quote_end']]!=candidate['quote']:raise ValueError('Quote mismatch')
                    all_candidates+=candidates;all_partials+=partials;all_blocks+=blocks;sources.append({k:v for k,v in meta.items() if k!='primary_text'})
    candidates=[c for c in all_candidates if c['source_url'] in wanted]
    result={'executed_at':datetime.now(timezone.utc).isoformat(),'method_version':'revenue-rules-v2','adapter_version':'pilot-exact-fact-calendar-v1','gold_sha256':seal['gold_sha256'],'sample_sha256':hashlib.sha256((ROOT/'sample.json').read_bytes()).hexdigest(),'scope':'All reviewed consolidated annual and quarterly revenue targets in 30 whole releases, including misses and abstentions; normalized absolute-dollar tolerance endpoints are eligible labels','score':score(gold['records'],candidates,True)}
    result['per_company']={c['ticker']:score([g for g in gold['records'] if g['company']==c['ticker']],[x for x in candidates if x['company']==c['ticker']],True)['strict_record'] for c in cs}
    formats=sorted({r['format'] for r in gold['release_reviews']});result['per_format']={}
    for fmt in formats:
        urls={r['source_url'] for r in gold['release_reviews'] if r['format']==fmt}
        result['per_format'][fmt]=score([g for g in gold['records'] if g['source_url'] in urls],[c for c in candidates if c['source_url'] in urls],True)['strict_record']
    strict=result['score']['strict_record'];tp=sum(m['exact'] for m in result['score']['matches'])
    result['counts']={'true_positive':tp,'emitted':len(candidates),'gold':len(gold['records']),'false_positive':len(candidates)-tp,'false_negative':len(gold['records'])-tp}
    result['precision_interval']=interval(tp,len(candidates));result['recall_interval']=interval(tp,len(gold['records']))
    result['abstentions']=[b for b in all_blocks if b['source_url'] in wanted];result['partials']=[p for p in all_partials if p['source_url'] in wanted];result['abstention_counts']=dict(Counter(b['code'] for b in result['abstentions']));result['source_gaps']=gaps
    result['gate_passed']=bool(candidates) and Decimal(tp)/len(candidates)>=Decimal('.98') and Decimal(tp)/len(gold['records'])>=Decimal('.90')
    result['candidates']=candidates
    with Path(output).open('x') as f:f.write(dumps(result)+'\n')
    write(CACHE_ROOT/'all-candidates.json',{'candidates':all_candidates,'partials':all_partials,'abstentions':all_blocks,'source_gaps':gaps,'sources':sources,'production':False})
    print(dumps({'counts':result['counts'],'strict_record':strict,'gate_passed':result['gate_passed']}))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();run(a.output)
