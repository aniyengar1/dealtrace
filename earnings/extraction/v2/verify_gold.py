"""Mechanical evidence checks independent of the candidate rules, not a semantic oracle."""
import hashlib,json,re
from pathlib import Path
from decimal import Decimal
from datetime import datetime,timezone
from earnings.sec import fetch
from earnings.extraction.corpus import canonical
from earnings.models import dumps
ROOT=Path(__file__).resolve().parent

def verify():
    raw=(ROOT/'fresh_gold.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=(ROOT/'fresh_gold.sha256').read_text().strip():raise ValueError('Fresh gold integrity failure')
    gold=json.loads(raw);checks=[]
    for g in gold['records']:
        body,m=fetch(g['source_url']);text=canonical(body);review=g['review']
        if m['sha256']!=review['raw_source_sha256'] or g['quote'] not in text:raise ValueError('Pinned source/quote mismatch')
        if review['dateline_quote'] not in text:raise ValueError('Dateline absent')
        scale=Decimal(1000000000) if review['numeric_transcription']['scale_word'].lower()=='billion' else Decimal(1000000)
        for key in ['low','high']:
            literal=review['numeric_transcription'][key+'_literal']
            if literal not in g['quote']:raise ValueError('Manually transcribed literal absent')
            if Decimal(literal.replace(',',''))*scale!=Decimal(g[key]):raise ValueError('Scale conversion mismatch')
        cal=review['calendar_crosscheck'];facts,manifest=fetch(cal['source_url']);j=json.loads(facts)
        found=False
        for concept in j['facts']['us-gaap'].values():
            for unit,rows in concept.get('units',{}).items():
                if unit=='USD' and any(r.get('start')==cal['start'] and r['end']==cal['end'] and r['accn']==cal['accession'] and r['filed']==cal['filed'] for r in rows):found=True
        if not found:raise ValueError('Independent fiscal-boundary fact absent')
        checks.append({'gold_id':g['id'],'company':g['company'],'source_sha256':m['sha256'],'quote_and_numeric_scale_verified':True,'fiscal_boundary_fact_verified':True})
    return {'checked_at':datetime.now(timezone.utc).isoformat(),'verifier':'Independent deterministic evidence checks, no v2 extraction imports','limitations':'These checks verify provenance and arithmetic; source semantics and column selection remain manually reviewed, not proven by quote matching. One curator, not a second independent human review.','records':checks}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();r=verify()
    with open(a.output,'x') as stream:stream.write(dumps(r)+'\n')
    print(dumps({'verified_records':len(r['records']),'output':a.output}))
