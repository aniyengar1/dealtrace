"""Dates-only research on official IR pages. Not live announcement evidence.

No models, SDKs, database, locks or production allowlist changes. Findings remain
unreviewed until full-article publication wording and datelines are adjudicated.
"""
import argparse,hashlib,json,re,time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,urljoin
import requests
from bs4 import BeautifulSoup
from src.fetch import USER_AGENT
from .scaling_2027q1_sources import save
ROOT=Path('data/cache/earnings/scaling-2027q1-dates')
HOSTS=dict(x.split('=',1) for x in '''ABNB=investors.airbnb.com ADI=investor.analog.com AEIS=ir.advancedenergy.com AKAM=www.ir.akamai.com AMAT=ir.appliedmaterials.com AMD=ir.amd.com AMPL=investors.amplitude.com AMZN=ir.aboutamazon.com APP=investors.applovin.com APPN=investors.appian.com AVPT=ir.avepoint.com BL=investors.blackline.com CNXC=ir.concentrix.com COHR=investor.coherent.com CRUS=investor.cirrus.com CTSH=investors.cognizant.com DIOD=investor.diodes.com DOCN=investors.digitalocean.com DOCS=investors.doximity.com ENPH=investor.enphase.com EPAM=investors.epam.com EW=ir.edwards.com FFIV=investors.f5.com FIVN=investors.five9.com FORM=investors.formfactor.com FTNT=investor.fortinet.com HIMS=investors.hims.com HLIT=investor.harmonicinc.com ICHR=ir.ichorsystems.com INTC=www.intc.com IPGP=investor.ipgphotonics.com KFRC=investor.kforce.com KLAC=ir.kla.com LITE=investor.lumentum.com LRCX=investor.lamresearch.com LSCC=ir.latticesemi.com MCHP=ir.microchip.com META=investor.atmeta.com MKSI=investor.mks.com MPWR=investors.monolithicpower.com MXL=investors.maxlinear.com NTAP=investors.netapp.com NTNX=ir.nutanix.com NVDA=investor.nvidia.com ON=investor.onsemi.com ONTO=investors.ontoinnovation.com PCTY=investors.paylocity.com PINS=investor.pinterestinc.com PLTR=investors.palantir.com PLXS=investor.plexus.com POWI=investors.power.com QLYS=investor.qualys.com RDDT=investor.redditinc.com RMBS=investor.rambus.com RNG=ir.ringcentral.com RPD=investors.rapid7.com SANM=ir.sanmina.com SEDG=investors.solaredge.com TASK=ir.taskus.com TDOC=ir.teladochealth.com TENB=investors.tenable.com TTMI=investors.ttm.com TWLO=investors.twilio.com ZS=ir.zscaler.com'''.split())
ANNOUNCE=re.compile(r'to (?:announce|report|release)|sets? (?:conference|earnings)|announces?.{0,50}(?:earnings date|date.{0,30}(?:results|earnings))|schedules?.{0,35}(?:earnings|results)',re.I)

def stamp():return datetime.now(timezone.utc).isoformat()
def observation(t,url):
    p=ROOT/t;p.mkdir(parents=True,exist_ok=True);key=hashlib.sha256(url.encode()).hexdigest();meta=p/(key+'.json')
    if meta.exists():return json.loads(meta.read_text())
    o={'url':url,'checked_at':stamp(),'purpose':'earnings-date announcement research only','status':'unverified'}
    try:
        current=url;redirects=[]
        for _ in range(4):
            response=requests.get(current,headers={'User-Agent':USER_AGENT},timeout=20,allow_redirects=False);o['http_status']=response.status_code
            if response.status_code in (301,302,307,308):
                nxt=urljoin(current,response.headers.get('Location',''));redirects.append({'from':current,'to':nxt,'status':response.status_code})
                # Record cross-host redirect, do not silently expand source scope.
                if urlparse(nxt).hostname!=urlparse(url).hostname:break
                current=nxt;continue
            if response.status_code==200:
                b=response.content;sha=hashlib.sha256(b).hexdigest();file=p/(key+'-'+sha+'.body');file.write_bytes(b);soup=BeautifulSoup(b,'html.parser');s=' '.join(soup.get_text(' ',strip=True).split());o.update(fetched_at=stamp(),sha256=sha,body_file=str(file),text=s,status='retrieved_not_semantically_verified',final_url=current,links=[{'text':a.get_text(' ',strip=True),'url':urljoin(current,a['href'])} for a in soup.find_all('a',href=True)])
            break
        o['redirects']=redirects
    except requests.RequestException as e:o['error']=type(e).__name__
    save(meta,o);return o

def collect(t):
    home='https://'+HOSTS[t];dest=ROOT/t;dest.mkdir(parents=True,exist_ok=True);done=dest/'inventory.json'
    if done.exists():return json.loads(done.read_text())
    first=observation(t,home+'/');pages=[first];links=first.get('links',[])
    candidates=[]
    for x in links:
        if urlparse(x['url']).hostname!=HOSTS[t]:continue
        if re.search(r'^(?:View (?:All )?)?(?:News|News Releases|Press Releases|Press|Investor News|Latest News)(?: & Events)?$',x['text'],re.I):candidates.append(x['url'])
    # Discovery probes remain unverified unless the full official page is retrieved.
    for path in ('/news/default.aspx','/news-events/press-releases','/news-releases'):
        if not candidates:candidates.append(home+path)
    seen={first['url']}
    for u in list(dict.fromkeys(candidates))[:3]:
        if u not in seen:pages.append(observation(t,u));seen.add(u)
    # Follow actual older-page links, with a research bound; incomplete coverage is recorded.
    for page in list(pages):
        nexts=[x['url'] for x in page.get('links',[]) if re.search(r'^Next|^2$|^3$|^4$',x['text'],re.I) and urlparse(x['url']).hostname==HOSTS[t]]
        for u in list(dict.fromkeys(nexts))[:3]:
            if u not in seen:pages.append(observation(t,u));seen.add(u)
    proposals=[]
    for page in pages:
        for x in page.get('links',[]):
            if ANNOUNCE.search(x['text']) and urlparse(x['url']).hostname==HOSTS[t] and x['url'] not in [a['url'] for a in proposals]:proposals.append(x)
    releases=[]
    for x in proposals[:16]:
        a=observation(t,x['url']);a['link_title']=x['text'];releases.append(a)
    r={'company':t,'official_ir_research_host':HOSTS[t],'began_at':first['checked_at'],'finished_at':stamp(),'inventory_pages':[{'url':x['url'],'http_status':x.get('http_status'),'error':x.get('error'),'sha256':x.get('sha256')} for x in pages],'announcement_proposals':[{'url':x['url'],'link_title':x.get('link_title'),'status':x['status'],'http_status':x.get('http_status'),'sha256':x.get('sha256')} for x in releases],'full_announcement_count':sum('text' in x for x in releases),'last_four_pairs_verified':False,'coverage_limit':'At most three discovered news inventories and linked older pages; not a complete-news or not-public attestation.'};save(done,r);print(t,len(releases),'announcement sources',r['full_announcement_count'],'retrieved',flush=True);return r

def main():
    p=argparse.ArgumentParser();p.add_argument('tickers',nargs='*');a=p.parse_args()
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(collect,a.tickers or list(HOSTS)))
if __name__=='__main__':main()
