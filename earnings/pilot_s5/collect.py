"""Resumable SEC release collection, without calling an extractor or writing a DB.

A group is a quarterly results release plus the following results release, which
is the target of directly issued next-quarter guidance. Mapping is provisional
until source review. Missing links/facts stay gaps, not synthetic observations.
"""
import argparse, hashlib, json, re
from datetime import date,datetime,timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from earnings.sec import fetch,CACHE
from earnings.models import dumps
from earnings.extraction.corpus import canonical

ROOT=Path(__file__).parent
CACHE_ROOT=CACHE/'pilot_s5'
SEED='crosscheck-session5-pilot-audit-v1'

def read(path):return json.loads(Path(path).read_text(),parse_float=Decimal)
def write(path,obj):Path(path).write_text(dumps(obj)+'\n')
def archive(cik,accession,filename):return f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{filename}'
def source_release(c,filing):
    u=archive(c['cik'],filing['accession'],filing['primary']);body,pm=fetch(u)
    soup=BeautifulSoup(body,'html.parser');links=[]
    for tr in soup.find_all('tr'):
        if re.search(r'\b99\.1\b',canonical(str(tr).encode())):
            for a in tr.find_all('a',href=True):
                link=urljoin(u,a['href'])
                if link.startswith('https://www.sec.gov/Archives/') and link not in links:links.append(link)
    exhibits=[]
    for link in links:
        raw,m=fetch(link)
        try:text=canonical(raw)
        except ValueError:continue
        # A format-neutral quarterly result screen, not guidance extraction.
        if not re.search(r'(?:quarter|quarterly|three months)',text[:7000],re.I):continue
        if not re.search(r'(?:financial results|quarter.*results|quarter.*earnings)',text[:3500],re.I):continue
        exhibits.append({'source_url':link,'exhibit':'99.1','manifest':m,'canonical_sha256':hashlib.sha256(text.encode()).hexdigest()})
    return {**filing,'company':c['ticker'],'primary_url':u,'primary_manifest':pm,'exhibits':exhibits}

def collect_company(c,cutoff):
    dest=CACHE_ROOT/(c['ticker']+'-collection.json')
    if dest.exists():return read(dest)
    payload,sm=fetch(f'https://data.sec.gov/submissions/CIK{c["cik"]}.json');sub=json.loads(payload);rec=sub['filings']['recent'];fs=[]
    for i,form in enumerate(rec['form']):
        if form in ('8-K','8-K/A') and '2.02' in rec.get('items',['']*len(rec['form']))[i] and '2024-01-01'<=rec['filingDate'][i]<=cutoff:
            fs.append({'accession':rec['accessionNumber'][i],'filed':rec['filingDate'][i],'primary':rec['primaryDocument'][i],'form':form})
    sources=[];gaps=[]
    # Fetch enough for eight completed targets plus preceding status context.
    # Same-day/amendment groups remain linked, not independent sampling units.
    for f in sorted(fs,key=lambda f:(f['filed'],f['accession']),reverse=True):
        try:r=source_release(c,f)
        except (ValueError,RuntimeError,OSError) as exc:gaps.append({**f,'gap':type(exc).__name__});continue
        if r['exhibits']:sources.append(r)
        else:gaps.append({**f,'gap':'NO_QUALIFYING_99_1_RESULT_EXHIBIT_LINK'})
        # Original quarterly result releases must be separated by >=35 days.
        dates=[]
        for s in sorted(sources,key=lambda s:s['filed'],reverse=True):
            if not dates or (date.fromisoformat(dates[-1])-date.fromisoformat(s['filed'])).days>=35:dates.append(s['filed'])
        if len(dates)>=11:break
    facts,fm=fetch(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{c["cik"]}.json')
    result={'company':c['ticker'],'cik':c['cik'],'collected_at':datetime.now(timezone.utc).isoformat(),'cutoff':cutoff,'submissions':sm,'companyfacts':fm,'releases':sources,'gaps':gaps}
    write(dest,result);return result

def groups(collection):
    originals=[]
    for r in sorted(collection['releases'],key=lambda r:(r['filed'],r['accession']),reverse=True):
        if r['form']=='8-K' and (not originals or (date.fromisoformat(originals[-1]['filed'])-date.fromisoformat(r['filed'])).days>=35):originals.append(r)
    out=[]
    # Guidance from previous release, outcome at next release; no guidance
    # issued with the classified result. Fiscal mapping verified by reviewer.
    for result,source in list(zip(originals,originals[1:]))[:8]:
        e=source['exhibits'][0]
        gid=collection['company']+':'+source['accession']
        out.append({'id':gid,'company':collection['company'],'source':source,'result':result,'status':'PENDING_MANUAL_GUIDANCE_AND_OUTCOME_BASIS_REVIEW','guidance_source_url':e['source_url'],'release_group':source['accession'],'amendments':[r for r in collection['releases'] if r['form']=='8-K/A' and source['filed']<=r['filed']<=result['filed']]})
    return out

def sample(groups):
    rank=lambda g:hashlib.sha256((SEED+'|'+g['id']).encode()).hexdigest()
    issuers=sorted({g['company'] for g in groups});chosen=[min([g for g in groups if g['company']==t],key=rank) for t in issuers]
    remaining=[g for g in groups if g['id'] not in {x['id'] for x in chosen}]
    chosen+=sorted(remaining,key=rank)[:30-len(chosen)]
    return sorted(chosen,key=lambda g:g['id'])

def run():
    plan=read(ROOT/'plan.json');cs=read(ROOT/'companies.json')['companies'];allgroups=[];coverage=[]
    for c in cs:
        r=collect_company(c,plan['cutoff']);gs=groups(r);allgroups+=gs
        coverage.append({'company':c['ticker'],'groups':len(gs),'guidance_filed_dates':[g['source']['filed'] for g in gs],'result_filed_dates':[g['result']['filed'] for g in gs],'gaps':r['gaps']})
        print(c['ticker'],len(gs),'completed target release pairs',flush=True)
    inventory={'groups':allgroups,'coverage':coverage}
    ip=ROOT/'inventory.json'
    if ip.exists():
        old=read(ip)
        if any(old[k]!=inventory[k] for k in inventory):raise ValueError('Frozen inventory drift; preserve existing audit and reserve a new version')
    else:write(ip,{'created_at':datetime.now(timezone.utc).isoformat(),**inventory})
    target=ROOT/'sample.json'
    reservation={'seed':SEED,'algorithm':'one minimum SHA256(seed|group-id) per company then ten globally ranked unused groups','created_at':datetime.now(timezone.utc).isoformat(),'inventory_sha256':hashlib.sha256((ROOT/'inventory.json').read_bytes()).hexdigest(),'groups':sample(allgroups)}
    if target.exists():
        old=read(target)
        if [g['id'] for g in old['groups']]!=[g['id'] for g in reservation['groups']]:raise ValueError('Frozen sample drift')
    else:write(target,reservation)

if __name__=='__main__':run()
