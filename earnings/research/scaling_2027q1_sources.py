"""Research-only SEC inventory. Never imports a store, model or live lock module.

No extraction acceptance or production promotion. Preserve source manifests and
all candidate exhibits for manual guidance/result/comparability adjudication.
python -m earnings.research.scaling_2027q1_sources [TICKER ...]
"""
import argparse,hashlib,io,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from earnings.sec import fetch

ROOT=Path('data/cache/earnings/scaling-2027q1-history')
UNIVERSE=Path('earnings/reports/scaling_universe_2027Q1.json')

def stamp():return datetime.now(timezone.utc).isoformat()
def text(body):
    if body.startswith(b'%PDF-'):
        from pypdf import PdfReader
        return ' '.join(' '.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(body)).pages).split())
    soup=BeautifulSoup(body,'html.parser')
    for hidden in soup.select('script,style,ix\\:header'):hidden.decompose()
    return ' '.join(soup.get_text(' ',strip=True).split())

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)

def document(url):
    try:
        b,m=fetch(url);return {'url':url,'manifest':m,'text':text(b)}
    except Exception as e:return {'url':url,'failed_at':stamp(),'error':type(e).__name__+':'+str(e)[:180]}

def exhibit_links(body,primary):
    soup=BeautifulSoup(body,'html.parser');links=[]
    for a in soup.find_all('a',href=True):
        label=a.get_text(' ',strip=True);url=urljoin(primary,a['href'])
        if not url.startswith('https://www.sec.gov/Archives/'):continue
        # Every labelled 99.x exhibit, including shareholder letters/slides; no
        # preference for easy release formats. Dedupe source URL only.
        if re.search(r'99\s*[.\-_]?\s*[123]|ex99|exhibit99|pressrelease|earningsrelease|shareholder',a['href']+' '+label+' '+(a.find_parent('tr').get_text(' ',strip=True) if a.find_parent('tr') else ''),re.I):
            if url not in links:links.append(url)
    return links

def collect(c,root=ROOT):
    t=c['ticker'];dest=root/t;dest.mkdir(parents=True,exist_ok=True)
    finished=dest/'inventory.json'
    if finished.exists():
        existing=json.loads(finished.read_text())
        if not existing['source_gaps'] and 'error' not in existing.get('companyfacts_source',{}) and existing['submissions_manifest']['fetched_at']>='2026-11-20T22:06:20+00:00' and existing.get('selection_definition')=='12-distinct-report-dates-v4':return existing
        finished.rename(dest/('inventory-failed-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json'))
    b,m=fetch(c['submissions']['url']);sub=json.loads(b);r=sub['filings']['recent'];events=[]
    for i,f in enumerate(r['form']):
        if f in ('8-K','8-K/A') and '2.02' in r['items'][i]:
            events.append({'accession':r['accessionNumber'][i],'filed':r['filingDate'][i],'report_date':r['reportDate'][i],'primary':r['primaryDocument'][i]})
    groups={}
    for e in events:
        key=e['report_date'] or e['filed']
        if key not in groups:groups[key]={**e,'related_accessions':[]}
        groups[key]['related_accessions'].append(e['accession'])
    events=sorted(groups.values(),key=lambda e:e['report_date'] or e['filed'],reverse=True)[:12] # distinct release dates; later inspect regular results vs preliminaries
    selected_accessions={a for e in events for a in e['related_accessions']}
    cutoff=min(r['filingDate'][i] for i,a in enumerate(r['accessionNumber']) if a in selected_accessions) if events else '2024-01-01'
    result={'selection_definition':'12-distinct-report-dates-v4','company':t,'cik':c['cik'],'began_at':stamp(),'submissions_manifest':m,'domestic_forms':sorted(set(r['form'])&{'10-K','10-Q','20-F','40-F'}),'events':events,'filings':[],'source_gaps':[],'eligible_quarters':None,'manual_review_status':'not_yet_adjudicated'}
    for i,f in enumerate(r['form']):
        if f not in ('8-K','8-K/A') or r['filingDate'][i]<cutoff:continue
        acc=r['accessionNumber'][i];fp=dest/(acc+'.json')
        if fp.exists():
            cached=json.loads(fp.read_text())
            if any('error' in d for d in [cached['primary']]+cached['exhibits']):fp.rename(dest/(acc+'-failed-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json'))
        if fp.exists():row=json.loads(fp.read_text())
        else:
            url=f'https://www.sec.gov/Archives/edgar/data/{int(c["cik"])}/{acc.replace("-","")}/{r["primaryDocument"][i]}';primary=document(url)
            row={'accession':acc,'filed':r['filingDate'][i],'report_date':r['reportDate'][i],'form':f,'items':r['items'][i],'primary':primary,'exhibits':[]}
            if 'text' in primary:
                relevant=('2.02' in row['items'] or re.search(r'guidance|outlook|revenue|preliminary|investor day|financial results|business update',primary['text'],re.I))
                if relevant:
                    raw,_=fetch(url)
                    for u in exhibit_links(raw,url):row['exhibits'].append(document(u))
                row['exhibit_review_scope']='all linked 99.x exhibits for earnings or potentially financial-guidance primary text' if relevant else 'primary screened; no guidance/publication terms found; exhibits not opened'
            save(fp,row)
        if 'text' in row['primary']:
            relevant=('2.02' in row['items'] or re.search(r'guidance|outlook|revenue|preliminary|investor day|financial results|business update',row['primary']['text'],re.I))
            if relevant:
                raw,_=fetch(row['primary']['url'])
                missing=[u for u in exhibit_links(raw,row['primary']['url']) if u not in {z['url'] for z in row['exhibits']}]
                if missing:
                    old=fp.with_name(fp.stem+'-before-link-review.json')
                    if not old.exists():save(old,row)
                    row['exhibits'].extend(document(u) for u in missing);save(fp,row)
        result['filings'].append({'accession':acc,'filed':row['filed'],'items':row['items'],'file':str(fp),'exhibit_count':len(row['exhibits'])})
        for doc in [row['primary']]+row['exhibits']:
            if 'error' in doc:result['source_gaps'].append({'accession':acc,**doc})
    facts_url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{c["cik"]}.json'
    try:
        _,fm=fetch(facts_url);facts={'url':facts_url,'manifest':fm}
    except Exception as e:facts={'url':facts_url,'error':type(e).__name__,'failed_at':stamp()}
    # JSON is kept in the transport cache; avoid duplicating a huge JSON string.
    facts.pop('text',None);result['companyfacts_source']=facts;result['finished_at']=stamp();save(finished,result)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('tickers',nargs='*');a=p.parse_args();data=json.loads(UNIVERSE.read_text());cs=[c for c in data['companies'] if c['readiness_tier']=='R1' and (not a.tickers or c['ticker'] in a.tickers)]
    embargo={x['company'] for x in json.loads(Path('earnings/hybrid/fresh_manifest.json').read_text())['issuers']}
    assert not embargo&{c['ticker'] for c in cs}
    for c in cs:
        try:
            r=collect(c);print(c['ticker'],len(r['events']),len(r['filings']),'filings',len(r['source_gaps']),'gaps',flush=True)
        except Exception as e:print(c['ticker'],'FAILED',type(e).__name__,str(e)[:150],flush=True)
if __name__=='__main__':main()
