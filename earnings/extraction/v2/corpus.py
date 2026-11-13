"""SEC bodies plus primary-document date evidence; no gold target values passed."""
import hashlib,json
from pathlib import Path
from earnings.sec import fetch,CACHE
from earnings.extraction.corpus import canonical
ROOT=Path(__file__).resolve().parent


def primary_urls():
    out={}
    for p in (ROOT.parents[1]/'history').glob('*.json'):
        for r in json.loads(p.read_text()).get('source_inventory',[]):out[r['accession']]=r['primary_url']
    reservation=json.loads((ROOT/'reservation.json').read_text())
    for g in reservation['groups']:
        for k in ['evaluation_release','context_release']:
            r=g.get(k)
            if r:out[r['accession']]=r['primary_url']
    return out


def materialize(doc):
    body,m=fetch(doc['source_url']);text=canonical(body)
    meta={**doc,'raw_sha256':m['sha256'],'fetched_at':m['fetched_at'],'canonical_sha256':hashlib.sha256(text.encode()).hexdigest()}
    primary=primary_urls().get(doc['accession'])
    if primary:
        b,pm=fetch(primary);meta.update(primary_url=primary,primary_text=canonical(b),primary_sha256=pm['sha256'],primary_fetched_at=pm['fetched_at'])
        meta['amendment']='8-K/A' in meta['primary_text'][:2500]
    directory=CACHE/'extraction-v2';directory.mkdir(exist_ok=True)
    path=directory/(meta['canonical_sha256']+'.txt');path.write_text(text);meta['canonical_cache']=str(path)
    return body,meta
