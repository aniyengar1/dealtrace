"""Build a source-only audit packet. Never import or invoke extraction rules."""
import hashlib,re
from pathlib import Path
from earnings.extraction.corpus import canonical
from .collect import ROOT,CACHE_ROOT,read,write

def raw(manifest):
    b=(CACHE_ROOT.parent/manifest['body']).read_bytes()
    if hashlib.sha256(b).hexdigest()!=manifest['sha256']:raise ValueError('Source hash drift')
    return b

def packet(group):
    s=group['source'];e=s['exhibits'][0];text=canonical(raw(e['manifest']));primary=canonical(raw(s['primary_manifest']))
    return {'id':group['id'],'company':group['company'],'source_url':e['source_url'],'filed':s['filed'],'accession':s['accession'],'source_sha256':e['manifest']['sha256'],'fetched_at':e['manifest']['fetched_at'],'canonical_sha256':hashlib.sha256(text.encode()).hexdigest(),'entire_canonical_text':text,'primary_text':primary,'instructions':'Read ALL guidance content; transcribe positive targets and negative/uncertain/implied records. No extractor output in packet.'}

def run():
    sample=read(ROOT/'sample.json');packets=[packet(g) for g in sample['groups']];out=CACHE_ROOT/'review-packet.json'
    write(out,{'sample_sha256':hashlib.sha256((ROOT/'sample.json').read_bytes()).hexdigest(),'packets':packets});print(str(out))

if __name__=='__main__':run()
