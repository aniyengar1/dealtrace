"""Immutable gold loading and SEC-only corpus materialization, no gold value inputs."""
import argparse,hashlib,json
from pathlib import Path
from bs4 import BeautifulSoup
from earnings.sec import fetch
from earnings.models import dumps
ROOT=Path(__file__).resolve().parent
CACHE=ROOT.parents[1]/'data/cache/earnings/extraction'


def gold():
    body=(ROOT/'gold_v1.json').read_bytes();split=json.loads((ROOT/'split_v1.json').read_text())
    if hashlib.sha256(body).hexdigest()!=split['gold_sha256']:raise ValueError('Frozen gold checksum mismatch')
    return json.loads(body)


def canonical(body):
    if body.lstrip().startswith(b'%PDF'):raise ValueError('PDF_REQUIRES_SEPARATE_TEXT_REVIEW')
    soup=BeautifulSoup(body,'html.parser',from_encoding='utf-8')
    for node in soup(['script','style','ix:header']):node.decompose()
    return ' '.join(soup.get_text(' ',strip=True).split())


def documents(split=None):
    docs={}
    for g in gold()['records']:
        if split and g['split']!=split:continue
        key=(g['company'],g['source_url'])
        d=docs.setdefault(key,{k:g[k] for k in ['company','source_url','accession','filed','exhibit','split']})
        if d['accession']!=g['accession'] or d['split']!=g['split']:raise ValueError('Release/source metadata conflict')
    return sorted(docs.values(),key=lambda d:(d['filed'],d['company'],d['source_url']))


def materialize(doc):
    body,manifest=fetch(doc['source_url']);text=canonical(body);sha=hashlib.sha256(text.encode()).hexdigest()
    CACHE.mkdir(parents=True,exist_ok=True);path=CACHE/(sha+'.txt')
    if path.exists() and path.read_text()!=text:raise ValueError('Canonical cache integrity failure')
    path.write_text(text)
    return text,{**doc,'raw_sha256':manifest['sha256'],'fetched_at':manifest['fetched_at'],'canonical_sha256':sha,'canonical_cache':str(path),'offset_basis':'Unicode code points in whitespace-collapsed BeautifulSoup visible text v1; half-open [start,end), not HTML bytes'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['development','heldout'],default='development');args=p.parse_args()
    for d in documents(args.split):
        try:t,m=materialize(d);print(dumps({'company':d['company'],'filed':d['filed'],'sha256':m['raw_sha256'],'characters':len(t)}))
        except ValueError as exc:print(dumps({'source_url':d['source_url'],'blocked':str(exc)}))
