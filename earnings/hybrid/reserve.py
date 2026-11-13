"""SEC submission metadata only. Does not retrieve any Archives release body."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from earnings.sec import fetch,CACHE
from earnings.models import dumps
ROOT=Path(__file__).parent

def reserve():
    plan=json.loads((ROOT/'reservation_plan.json').read_text());out=ROOT/'fresh_manifest.json'
    if out.exists():raise ValueError('Preserve frozen reservation; no overwrite')
    # Read only our URL manifests and tracked research JSON strings for exposure.
    known_urls=[]
    for p in CACHE.glob('*.manifest.json'):
        try:known_urls.append(json.loads(p.read_text()).get('url',''))
        except (ValueError,OSError):continue
    for p in (ROOT.parent).rglob('*.json'):
        if ROOT in p.parents:continue
        text=p.read_text()
        import re
        known_urls.extend(re.findall(r'https://www\.sec\.gov/Archives/edgar/data/[^"\s]+',text))
    tickers,tm=fetch('https://www.sec.gov/files/company_tickers.json');ids={v['ticker']:str(v['cik_str']).zfill(10) for v in json.loads(tickers).values()};issuers=[]
    for ticker in plan['issuer_order']:
        if ticker not in ids:
            issuers.append({'company':ticker,'status':'METADATA_GAP_NO_CURRENT_SEC_TICKER_MATCH'});continue
        cik=ids[ticker];prefix=f'/edgar/data/{int(cik)}/'
        if any(prefix in url for url in known_urls):
            issuers.append({'company':ticker,'cik':cik,'status':'EXCLUDED_PRIOR_RELEASE_URL_EXPOSURE'});continue
        b,m=fetch(f'https://data.sec.gov/submissions/CIK{cik}.json');sub=json.loads(b);parts=[sub['filings']['recent']];manifests=[m]
        for f in sub['filings'].get('files',[]):
            if f['filingFrom']<='2024-12-31' and f['filingTo']>='2024-01-01':
                bb,mm=fetch('https://data.sec.gov/submissions/'+f['name']);parts.append(json.loads(bb));manifests.append(mm)
        rows={}
        for rec in parts:
            for i,form in enumerate(rec['form']):
                filed=rec['filingDate'][i]
                if form not in ('8-K','8-K/A') or not '2024-01-01'<=filed<='2024-12-31':continue
                items=rec.get('items',['']*len(rec['form']))[i]
                if '2.02' not in items:continue
                acc=rec['accessionNumber'][i];primary=rec['primaryDocument'][i]
                rows[acc]={'accession':acc,'filed':filed,'form':form,'report_date':rec.get('reportDate',['']*len(rec['form']))[i],'items':items,'primary_url':f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-","")}/{primary}','release_group':ticker+':'+rec.get('reportDate',['']*len(rec['form']))[i],'release_body_opened':False,'labels_created':False,'inference_performed':False}
        issuers.append({'company':ticker,'cik':cik,'name':sub['name'],'status':'RESERVED_METADATA_ONLY' if rows else 'METADATA_GAP','submissions_manifests':manifests,'releases':sorted(rows.values(),key=lambda r:(r['filed'],r['accession']))})
        print(ticker,len(rows),'metadata records; bodies unopened',flush=True)
    result={'reserved_at':datetime.now(timezone.utc).isoformat(),'plan_sha256':hashlib.sha256((ROOT/'reservation_plan.json').read_bytes()).hexdigest(),'tickers_manifest':tm,'issuers':issuers,'embargo':'No body fetch, label creation or fresh inference in diagnostic stage. Entire reserved issuer is excluded from prompt development.'}
    with out.open('x') as f:f.write(dumps(result)+'\n')

if __name__=='__main__':reserve()
