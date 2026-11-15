"""Timing/publication evidence and immutable live-ledger persistence."""
from datetime import datetime, date, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib,json,re
import requests
from bs4 import BeautifulSoup
from psycopg.types.json import Jsonb

from . import store
from .models import plain, digest
from .registry import ROOT
from .baseline import aware, guidance_cutoff
from .dates import check_source, IR_HOSTS
from .sec import fetch,CACHE
from src.fetch import USER_AGENT
from .actuals import Blocked
from uuid import UUID
from urllib.parse import urljoin

WATCH={
 'PD':'https://investor.pagerduty.com/news/default.aspx',
 'GTLB':'https://ir.gitlab.com/news/default.aspx',
 'CRM':'https://investor.salesforce.com/news/default.aspx',
 'CRWD':'https://ir.crowdstrike.com/news-and-events/news-releases',
 'OKTA':'https://investor.okta.com/news-and-events/news-releases/default.aspx',
 'IOT':'https://investors.samsara.com/news/default.aspx',
 'MDB':'https://investors.mongodb.com/news-events/news-releases',
 'S':'https://investors.sentinelone.com/press-releases/',
 'ADBE':'https://www.adobe.com/investor-relations.html',
 'LULU':'https://corporate.lululemon.com/investors/news-and-events/press-releases'}
WORDS={1:'first',2:'second',3:'third',4:'fourth'}


def announcement(company):
    p=ROOT/'announcements'/f'{company["ticker"]}.json'
    if not p.exists():
        raise Blocked('UNVERIFIED_RELEASE_DATE','No independently retrieved full-document or direct user-verified results-publication evidence. Calls, calendar estimates and other-agent/search leads do not qualify.')
    rows=json.loads(p.read_text())['versions']
    rows=[r for r in rows if r['event_kind']=='results_release' and r['fiscal_period']['end']==company['quarter_targets'][-1]['end']]
    if not rows:raise Blocked('UNVERIFIED_RELEASE_DATE','No evidence for exact target quarter')
    return max(rows,key=lambda r:aware(r.get('verified_at',r.get('entered_at'))))


def deadline(evidence):
    if evidence.get('verification_status') not in ('independently_verified','user_verified') or evidence.get('event_kind')!='results_release':
        raise Blocked('UNVERIFIED_RELEASE_DATE','Verified results publication, not call timing, required')
    if not evidence.get('timezone'):raise Blocked('UNRESOLVED_TIMEZONE','Release-day timezone is unknown')
    zone=ZoneInfo(evidence['timezone']);day=date.fromisoformat(evidence['release_date'])
    if evidence.get('timestamp_verified') and evidence['time_precision'] in ('minute','second'):
        if evidence.get('timestamp_kind')!='results_publication' or not evidence.get('timestamp_source_quote'):
            raise Blocked('UNVERIFIED_PUBLICATION_TIME','Exact timestamp must refer to results publication')
        value=aware(evidence['release_timestamp'])
        if value.astimezone(zone).date()!=day:raise Blocked('UNRESOLVED_TIMEZONE','Release timestamp and date do not agree')
        return value
    # Before-open / after-close are not exact times. Never substitute 09:30.
    return datetime.combine(day,time.min,zone).astimezone(timezone.utc)


def verify_durable(company,evidence):
    """Integrity and provenance only; historical retrieval time never refreshed."""
    target=company['quarter_targets'][-1]
    if evidence.get('company')!=company['ticker'] or any(evidence.get('fiscal_period',{}).get(k)!=target[k] for k in ('start','end')):
        raise Blocked('DURABLE_EVIDENCE_TARGET_MISMATCH','Exact issuer and target fiscal period required')
    if evidence.get('verification_status')=='user_verified' and evidence.get('verification_method')=='owner_pdf_document_review_v1':
        from .owner_evidence import refresh
        try:return refresh(company,evidence)
        except (OSError,ValueError,KeyError) as exc:raise Blocked('DURABLE_EVIDENCE_INTEGRITY_GAP',type(exc).__name__) from exc
    path=evidence.get('cached_body')
    if not path or not Path(path).resolve().is_relative_to(CACHE.resolve()):
        raise Blocked('DURABLE_EVIDENCE_MISSING','Preserved official source body required')
    try:body=Path(path).read_bytes()
    except OSError as exc:raise Blocked('DURABLE_EVIDENCE_MISSING','Preserved source body unavailable') from exc
    if hashlib.sha256(body).hexdigest()!=evidence.get('source_sha256'):
        raise Blocked('DURABLE_EVIDENCE_INTEGRITY_GAP','Preserved announcement bytes changed')
    return dict(evidence)

def refresh_announcement(company,evidence):
    evidence=verify_durable(company,evidence)
    if evidence.get('verification_method')=='owner_pdf_document_review_v1':
        raise Blocked('CURRENT_STATE_CHECK_REQUIRED','Historical owner PDF is valid durable evidence; supply a fresh owner-browser current-state check, not a new PDF retrieval')
    check=check_source(company['ticker'],evidence['source_url'],source_date=evidence['announcement_issued_date'],report_date=evidence['release_date'])
    if check['status']!='confirmed':raise Blocked('ANNOUNCEMENT_ACCESS_GAP','Fresh full official announcement could not be verified: '+str(check.get('http_status',check.get('error_type',check['status']))))
    if check['sha256']!=evidence.get('source_sha256'):
        raise Blocked('ANNOUNCEMENT_SOURCE_CHANGED','The source body changed; review and append new evidence instead of reusing or rewriting the old date.')
    # Durable provenance is unchanged. New HTTP observation is a separate check.
    target=company['quarter_targets'][-1]
    current={'policy_version':'current-state-checks-v2','method':'automated_http','status':'unchanged',
        'checked_at':check['checked_at'],'company':company['ticker'],'target_start':target['start'],'target_end':target['end'],
        'source_url':evidence['source_url'],'verification_status':'independently_verified',
        'observed_schedule':{k:evidence.get(k) for k in ('release_date','timezone','time_precision','release_time','release_timestamp','timestamp_kind','timestamp_source_quote')},'http_check':check}
    return {**evidence,'prelock_schedule_check':current}


def sec_publication_check(company,target):
    result={'success':False,'status':'unverified','checked_at':datetime.now(timezone.utc).isoformat()}
    try:
        b,m=fetch(f'https://data.sec.gov/submissions/CIK{company["cik"]}.json',refresh=True)
        filings=json.loads(b)['filings']['recent'];suspects=[]
        for i,form in enumerate(filings['form']):
            if form in ('8-K','8-K/A','10-Q','10-K') and filings['filingDate'][i]>=target['end']:
                if form in ('10-Q','10-K') or '2.02' in filings.get('items',['']*len(filings['form']))[i]:
                    suspects.append({'form':form,'filed':filings['filingDate'][i],'accession':filings['accessionNumber'][i]})
        result.update(success=True,status='possible_results' if suspects else 'clear',manifest=m,possible_results_filings=suspects)
    except (requests.RequestException,RuntimeError,ValueError,OSError) as exc:result['error_type']=type(exc).__name__
    return result


def publication_check(company,target):
    """Fail-closed SEC + official IR metadata check, never reads IR financial values.

    A loading/empty/dynamic listing cannot establish an observable news inventory.
    Source absence is not a guarantee against undisclosed/third-party publication.
    """
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'target_start':target['start'],'target_end':target['end'],
            'policy_version':'current-state-checks-v2','status':'unverified','sec':{'success':False},'official_ir':{'success':False},'verifier':'Crosscheck publication-metadata checker v1'}
    try:
        result['sec']=sec_publication_check(company,target)
        if not result['sec']['success']:return result
        if result['sec']['status']!='clear':result['status']='already_public_or_unresolved_sec_results';return result
        url=WATCH[company['ticker']]
        if url.split('/')[2] not in IR_HOSTS[company['ticker']]:raise ValueError('Official source outside allowlist')
        response=requests.get(url,headers={'User-Agent':USER_AGENT},timeout=20,allow_redirects=False)
        result['official_ir']={'success':False,'source_url':url,'http_status':response.status_code}
        if response.status_code!=200:return result
        body=response.content;soup=BeautifulSoup(body,'html.parser');text=' '.join(soup.get_text(' ',strip=True).split())
        sha=hashlib.sha256(body).hexdigest();p=CACHE/'publication-checks';p.mkdir(parents=True,exist_ok=True);(p/(sha+'.body')).write_bytes(body)
        titles=[' '.join(n.get_text(' ',strip=True).split()) for n in soup.find_all(['a','h1','h2','h3','h4'])]
        q=int(re.search(r'Q([1-4])',target['label'])[1]);fy=re.search(r'FY(\d{4})',target['label'])[1]
        suspect=[s for s in titles if (WORDS[q]+' quarter' in s.lower() or re.search(r'Q\s*'+str(q),s)) and
            (fy in s or 'FY'+fy[-2:] in s) and any(x in s.lower() for x in ('results','revenue','earnings')) and
            not any(x in s.lower() for x in ('announces date','to announce','conference call','earnings call','webcast','guidance','outlook'))]
        result['official_ir'].update(sha256=sha,checked_at=result['checked_at'],retrieved_at=datetime.now(timezone.utc).isoformat(),possible_results_titles=suspect,method='automated_http')
        if suspect:result['status']='already_public_or_unresolved_ir_results';return result
        try:known=announcement(company)['source_url']
        except Blocked:known=None
        notices=[{'title':' '.join(a.get_text(' ',strip=True).split()),'url':urljoin(url,a['href'])} for a in soup.find_all('a',href=True)
            if (WORDS[q]+' quarter' in a.get_text(' ',strip=True).lower() or re.search(r'Q\s*'+str(q),a.get_text())) and
            (fy in a.get_text() or 'FY'+fy[-2:] in a.get_text()) and
            any(w in a.get_text().lower() for w in ('to announce','announces date','reschedul','postpon','delay')) and urljoin(url,a['href'])!=known]
        result['official_ir']['possible_schedule_notices']=notices
        if notices:result['status']='schedule_update_or_unresolved_ir_notice';return result
        # An accessible, dated news inventory is required, not a JS loading shell.
        dated=bool(re.search(r'(?:20\d{2}[-/]\d{2}[-/]\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+20\d{2})',text))
        news=any('financial results' in s.lower() or 'reports' in s.lower() for s in titles)
        if dated and news:
            result['official_ir']['success']=True;result['status']='not_observed'
        else:result['official_ir']['gap']='No complete observable dated results/news list; no inference from a loading/empty page'
    except (requests.RequestException,RuntimeError,ValueError,OSError) as exc:
        result['error_type']=type(exc).__name__
    return result


def insert_prediction(conn,company,target,guidance,baseline,evidence,check):
    snapshot={'baseline':plain(baseline),'prediction_kind':'prospective_live','guidance_selection_rule':'latest fully public before the 14-day entry date',
              'latest_registry_target':target,'threat_model_version':'application-role-immutable-v1'}
    p=baseline['probabilities']
    row=conn.execute('''INSERT INTO earnings_live_predictions(company_id,metric,period_start,period_end,method_version,
      guidance_id,historical_ids,p_below,p_within,p_above,announcement,publication_check,snapshot,lock_deadline)
      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ON CONFLICT(company_id,period_start,period_end,metric,method_version) DO NOTHING
      RETURNING id,made_at,lock_deadline''',
      (store.company_id(company['ticker']),'quarterly_consolidated_revenue',target['start'],target['end'],baseline['method_version'],
       guidance.id,[UUID(v) for v in baseline['historical_ids']],p['below'],p['within'],p['above'],Jsonb(plain(evidence)),Jsonb(plain(check)),
       Jsonb(snapshot),deadline(evidence))).fetchone()
    return {'id':str(row[0]),'made_at':row[1].astimezone(timezone.utc).isoformat(),'lock_deadline':row[2].astimezone(timezone.utc).isoformat()} if row else None
