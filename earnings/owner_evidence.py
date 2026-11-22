"""Append owner-supplied announcement evidence; hashes do not prove authenticity.

PDF contents are untrusted evidence. No network access, OCR, scripts, or dates
inferred from expected schedules. No source or verification timestamp backdating.
"""
import argparse,fcntl,hashlib,io,json,os,re,uuid
from datetime import datetime,date,timezone,timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from .baseline import aware
from .models import record_id,dumps
from .dates import IR_HOSTS
from .sec import CACHE
from .registry import ROOT,companies
from .actuals import Blocked
CACHE_ROOT=CACHE/'owner-announcements'

def stamp():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(s):return ' '.join(s.split())
def save_new(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:f.write(dumps(value)+'\n')

def ingest(pdf,metadata,*,root=CACHE_ROOT):
    if set(metadata)!={'company','supplied_by','source_url','owner_retrieved_at'}:raise ValueError('Supply only company, supplied_by, source_url, owner_retrieved_at')
    ticker=metadata['company'];url=urlparse(metadata['source_url']);now=stamp()
    if ticker not in companies() or not metadata['supplied_by'].strip():raise ValueError('Supported company and supplier required')
    if url.scheme!='https' or url.hostname not in IR_HOSTS[ticker] or url.username or url.password or url.port:raise ValueError('Original official IR URL required')
    if aware(metadata['owner_retrieved_at'])>aware(now):raise ValueError('Owner retrieval cannot be in the future')
    body=Path(pdf).read_bytes()
    if not body.startswith(b'%PDF-') or len(body)>20_000_000:raise ValueError('PDF up to 20MB required')
    digest=sha(body);directory=root/'files';directory.mkdir(parents=True,exist_ok=True);dest=directory/(digest+'.pdf')
    if dest.exists():
        if sha(dest.read_bytes())!=digest:raise ValueError('Preserved file integrity failure')
    else:
        with dest.open('xb') as f:f.write(body)
    gaps=[];text=''
    try:
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(body))
        if reader.is_encrypted or len(reader.pages)>200:gaps.append('ENCRYPTED_OR_TOO_MANY_PAGES')
        else:text=canonical('\n'.join(p.extract_text() or '' for p in reader.pages))
        if not text:gaps.append('NO_EXTRACTABLE_TEXT_OCR_OR_MANUAL_TRANSCRIPTION_NEEDED')
    except Exception as exc:gaps.append('PDF_TEXT_EXTRACTION_FAILED:'+type(exc).__name__)
    result={**metadata,'id':str(uuid.uuid4()),'ingested_at':now,'original_filename':Path(pdf).name,
        'pdf_sha256':digest,'preserved_file':str(dest),'canonical_text':text,'canonical_sha256':sha(text.encode()),
        'gaps':gaps,'status':'document_review_required','verification_provenance':'owner_supplied_file_not_independently_HTTP_retrieved',
        'authenticity_limit':'SHA-256 proves byte integrity, not document authenticity or current website contents'}
    save_new(root/'intakes'/(result['id']+'.json'),result)
    return result

def load_intake(identifier,root):
    identifier=str(uuid.UUID(identifier))
    return json.loads((root/'intakes'/(identifier+'.json')).read_text())

def date_supported(day,text):
    d=date.fromisoformat(day)
    return any(s in text for s in (d.strftime('%B ')+str(d.day)+d.strftime(', %Y'),d.strftime('%b ')+str(d.day)+d.strftime(', %Y'),str(d)))

def review(identifier,data,*,root=CACHE_ROOT):
    intake=load_intake(identifier,root);text=intake['canonical_text'];c=companies()[intake['company']];target=c['quarter_targets'][-1]
    required={'announcement_issued_date','release_date','release_time','time_precision','timezone','timezone_provenance','quotes','reviewed_by','review_note'}
    if set(data)!=required:raise ValueError('Review fields mismatch; timestamps are generated, not accepted')
    quotes=data['quotes'];needed={'company','fiscal_period','announcement_date','release_date','results_publication','release_time'}
    gaps=list(intake['gaps'])
    if set(quotes)!=needed:gaps.append('MISSING_REVIEW_EVIDENCE_ROLES')
    for role in needed:
        if not isinstance(quotes.get(role),str) or not canonical(quotes[role]) or canonical(quotes[role]) not in text:gaps.append('QUOTE_NOT_IN_PDF:'+role)
    name='crowdstrike' if c['ticker']=='CRWD' else 'mongodb' if c['ticker']=='MDB' else c['name'].split()[0].lower()
    if name not in quotes.get('company','').lower():gaps.append('COMPANY_IDENTITY_MISMATCH')
    label=target['label'];q=re.search(r'Q([1-4])',label)[1];year=re.search(r'FY(\d{4})',label)[1];fp=quotes.get('fiscal_period','').lower()
    if year not in fp or not (('q'+q) in fp or {1:'first',2:'second',3:'third',4:'fourth'}[int(q)]+' quarter' in fp):gaps.append('FISCAL_PERIOD_MISMATCH')
    for field,role in [('announcement_issued_date','announcement_date'),('release_date','release_date')]:
        if not date_supported(data[field],quotes.get(role,'')):gaps.append('DATE_NOT_SUPPORTED:'+field)
    if date.fromisoformat(data['announcement_issued_date'])>date.fromisoformat(data['release_date']):gaps.append('ANNOUNCEMENT_AFTER_RELEASE_DATE')
    publication=quotes.get('results_publication','').lower()
    if not ('results' in publication and re.search(r'\b(?:announce|release|report|publish)\b',publication)) or ('call' in publication and 'financial results' not in publication):gaps.append('RESULTS_PUBLICATION_WORDING_NOT_ESTABLISHED')
    if data['time_precision'] not in ('date','market_session'):gaps.append('UNSUPPORTED_TIME_PRECISION_REVIEW')
    if data['time_precision']=='market_session':
        timing=quotes.get('release_time','').lower()
        if data['release_time']!='after_market_close' or 'after' not in timing or 'close' not in timing:gaps.append('MARKET_SESSION_NOT_SUPPORTED')
    elif data['release_time'] is not None:gaps.append('DATE_ONLY_REQUIRES_NULL_TIME')
    ZoneInfo(data['timezone'])
    if not data['reviewed_by'].strip() or not data['timezone_provenance'].strip():gaps.append('REVIEWER_OR_TIMEZONE_PROVENANCE_MISSING')
    now=stamp();e={**data,'company':c['ticker'],'fiscal_period':{k:target[k] for k in ('start','end','label')},
        'event_kind':'results_release','verification_status':'user_verified' if not gaps else 'unverified',
        'owner_intake_id':identifier,'supplied_by':intake['supplied_by'],'source_url':intake['source_url'],
        'owner_retrieved_at':intake['owner_retrieved_at'],'ingested_at':intake['ingested_at'],
        'verified_at':now,'entered_at':now,'checked_at':now,'source_sha256':intake['pdf_sha256'],
        'verifier':data['reviewed_by'],'verification_method':'owner_pdf_document_review_v1',
        'independently_checked':False,'timestamp_verified':False,'gaps':gaps,
        'quote':quotes.get('results_publication'),'authenticity_limit':intake['authenticity_limit']}
    e['id']=record_id('owner-announcement-review-v1',e);save_new(root/'reviews'/(e['id']+'.json'),e)
    return e

def append(evidence,*,directory=ROOT/'announcements'):
    if evidence['verification_status']!='user_verified' or evidence['gaps']:raise ValueError('Unresolved document review cannot be promoted')
    directory.mkdir(parents=True,exist_ok=True);p=directory/(evidence['company']+'.json')
    with p.with_suffix('.lock').open('a') as f:
        fcntl.flock(f,fcntl.LOCK_EX);data=json.loads(p.read_text()) if p.exists() else {'company':evidence['company'],'versions':[]}
        if not any(x['id']==evidence['id'] for x in data['versions']):
            data['versions'].append(evidence);temp=p.with_suffix('.tmp');temp.write_text(dumps(data)+'\n');os.replace(temp,p)

def refresh(company,evidence,*,root=CACHE_ROOT):
    intake=load_intake(evidence['owner_intake_id'],root)
    reviewed=json.loads((root/'reviews'/(str(uuid.UUID(evidence['id']))+'.json')).read_text())
    path=root/'files'/(intake['pdf_sha256']+'.pdf')
    if company['ticker']!=intake['company'] or sha(path.read_bytes())!=evidence['source_sha256'] or reviewed!=evidence:
        raise Blocked('OWNER_EVIDENCE_INTEGRITY_GAP','Owner file/review identity or hash changed; append new evidence')
    if evidence['verification_status']!='user_verified' or evidence['gaps']:raise Blocked('OWNER_EVIDENCE_REVIEW_GAP','Complete document review required')
    return {**evidence,'integrity_check':{'kind':'local_owner_file_integrity_not_current_state_verification',
        'integrity_checked_at':stamp(),'source_retrieval_time_unchanged':intake['owner_retrieved_at'],'pdf_sha256':intake['pdf_sha256']}}


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('ingest');a.add_argument('--pdf',type=Path,required=True);a.add_argument('--metadata',type=Path,required=True)
    a=sub.add_parser('review');a.add_argument('--intake-id',required=True);a.add_argument('--review',type=Path,required=True);a.add_argument('--append',action='store_true')
    args=p.parse_args()
    if args.command=='ingest':r=ingest(args.pdf,json.loads(args.metadata.read_text()));print(dumps({k:v for k,v in r.items() if k!='canonical_text'}))
    else:
        r=review(args.intake_id,json.loads(args.review.read_text()))
        if args.append:append(r)
        print(dumps(r))
