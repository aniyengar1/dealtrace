"""Owner-assisted current-state checks, distinct from durable announcements.

No browser automation or inferred attestations. Intake uses actual receipt time;
owner page times remain attributed observations, not independently HTTP verified.
"""
import argparse,json,hashlib
from datetime import datetime,timezone,timedelta,date
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from .baseline import aware
from .models import record_id,dumps
from .actuals import Blocked
from .dates import IR_HOSTS
from .registry import companies
from .sec import CACHE
POLICY='current-state-checks-v2'
DIRECTORY=CACHE/'current-checks'
ROLES={'schedule','news_inventory','results_inventory'}

def now():return datetime.now(timezone.utc)
def official(ticker,url):
    try:
        u=urlparse(url)
        return u.scheme=='https' and u.hostname in IR_HOSTS[ticker] and not(u.username or u.password or u.port)
    except (ValueError,TypeError,KeyError):return False

def assess(data,company,evidence,clock):
    clock=aware(clock);target=company['quarter_targets'][-1];gaps=[];times=[];roles=set()
    required={'company','announcement_id','observer','timezone','precision','pages','schedule','publication','attestation','personally_checked','automation_gap','contradictions'}
    if set(data)!=required:gaps.append('ATTESTATION_FIELDS_INCOMPLETE')
    if data.get('company')!=company['ticker'] or data.get('announcement_id')!=evidence['id']:gaps.append('ANNOUNCEMENT_IDENTITY_MISMATCH')
    if not isinstance(data.get('observer'),str) or not data['observer'].strip() or not isinstance(data.get('attestation'),str) or not data['attestation'].strip() or data.get('personally_checked') is not True:gaps.append('OWNER_ATTRIBUTION_OR_ATTESTATION_MISSING')
    if data.get('contradictions')!=[]:gaps.append('CONTRADICTORY_OR_UNRESOLVED_EVIDENCE')
    try:zone=ZoneInfo(data.get('timezone',''))
    except (ValueError,TypeError,KeyError):zone=None;gaps.append('CHECK_TIMEZONE_UNRESOLVED')
    if data.get('precision') not in ('second','minute'):gaps.append('CHECK_TIME_PRECISION_UNRESOLVED')
    pages=data.get('pages')
    if not isinstance(pages,list) or not pages:gaps.append('PAGES_MISSING');pages=[]
    for p in pages:
        if not isinstance(p,dict):gaps.append('PAGE_INVALID');continue
        if not official(company['ticker'],p.get('url')) or ('final_url' in p and not official(company['ticker'],p['final_url'])):gaps.append('NONOFFICIAL_PAGE_URL')
        rs=p.get('roles',[])
        if not isinstance(rs,list) or not rs or not all(isinstance(x,str) for x in rs) or not set(rs)<=ROLES:gaps.append('PAGE_ROLE_INVALID');rs=[]
        roles.update(rs)
        if not isinstance(p.get('coverage'),str) or not p['coverage'].strip() or p.get('complete') is not True:gaps.append('PAGE_COVERAGE_INCOMPLETE')
        if 'schedule' in rs and p.get('url')!=evidence['source_url']:gaps.append('SCHEDULE_SOURCE_URL_MISMATCH')
        try:
            t=aware(p['checked_at']);original=datetime.fromisoformat(p['checked_at'].replace('Z','+00:00'))
            if zone is not None and original.utcoffset()!=t.astimezone(zone).utcoffset():gaps.append('CHECK_TIMEZONE_OFFSET_MISMATCH')
            if data.get('precision')=='minute' and (t.second or t.microsecond):gaps.append('CHECK_PRECISION_MISMATCH')
            if t>clock:gaps.append('FUTURE_CHECK_TIME')
            times.append(t)
        except (ValueError,TypeError,KeyError):gaps.append('PAGE_TIME_MISSING_OR_INVALID')
    if not ROLES<=roles:gaps.append('REQUIRED_COVERAGE_MISSING')
    checked=min(times) if times else None
    if checked is None or clock-checked>timedelta(minutes=10):gaps.append('STALE_CURRENT_CHECK')
    schedule=data.get('schedule',{})
    if not isinstance(schedule,dict):schedule={};gaps.append('SCHEDULE_FIELDS_MISSING')
    if schedule.get('time_precision') not in ('date','market_session','minute','second'):gaps.append('PUBLICATION_TIMING_UNRESOLVED')
    for field in ('release_date','timezone','time_precision','release_time'):
        if schedule.get(field)!=evidence.get(field):gaps.append('SCHEDULE_CHANGED_OR_UNRESOLVED:'+field)
    if schedule.get('event_kind')!='results_release':gaps.append('RESULTS_PUBLICATION_NOT_ESTABLISHED')
    if evidence.get('timestamp_verified'):
        for field in ('release_timestamp','timestamp_kind','timestamp_source_quote'):
            if not schedule.get(field) or schedule.get(field)!=evidence.get(field):gaps.append('EXACT_PUBLICATION_TIME_UNRESOLVED')
    pub=data.get('publication',{})
    if not isinstance(pub,dict):pub={};gaps.append('PUBLICATION_FIELDS_MISSING')
    if pub.get('status')!='not_observed':gaps.append('RESULTS_ALREADY_PUBLIC_OR_UNRESOLVED')
    if (pub.get('target_start'),pub.get('target_end'))!=(target['start'],target['end']):gaps.append('TARGET_PERIOD_MISMATCH')
    if pub.get('preliminary_results_checked') is not True or pub.get('pagination_complete') is not True:gaps.append('PUBLICATION_COVERAGE_INCOMPLETE')
    try:
        if date.fromisoformat(pub['coverage_from'])>date.fromisoformat(target['start']) or zone is None or date.fromisoformat(pub['coverage_through'])!=clock.astimezone(zone).date():gaps.append('PUBLICATION_DATE_COVERAGE_INCOMPLETE')
    except (ValueError,KeyError,TypeError):gaps.append('PUBLICATION_DATE_COVERAGE_INCOMPLETE')
    gap=data.get('automation_gap',{})
    if not isinstance(gap,dict) or not official(company['ticker'],gap.get('url')) or not gap.get('reason') or gap.get('provenance')!='owner_reported':gaps.append('AUTOMATION_GAP_PROVENANCE_MISSING')
    return {'policy_version':POLICY,'status':'usable' if not gaps else 'blocked','gaps':sorted(set(gaps)),
        'checked_at':checked.isoformat() if checked else None,'checked_at_kind':'earliest_owner_reported_page_check','verification_status':'user_verified' if not gaps else 'unverified','independently_http_verified':False}

def intake(path,*,directory=DIRECTORY):
    from .live import announcement
    body=Path(path).read_bytes();data=json.loads(body);company=companies()[data['company']];clock=now()
    result={'policy_version':POLICY,'data':data,'input_sha256':hashlib.sha256(body).hexdigest(),
        'ingested_at':clock.isoformat(),'assessment':assess(data,company,announcement(company),clock)}
    result['id']=record_id('owner-current-check-v2',result)
    directory.mkdir(parents=True,exist_ok=True)
    raw=directory/'inputs';raw.mkdir(exist_ok=True);original=raw/(result['input_sha256']+'.json')
    if not original.exists():
        with original.open('xb') as f:f.write(body)
    with (directory/(result['id']+'.json')).open('x') as f:f.write(dumps(result)+'\n')
    return result

def validate_record(record,company,evidence,clock):
    if not isinstance(record,dict) or not {'id','data','ingested_at','assessment'}<=set(record) or not isinstance(record['assessment'],dict):raise Blocked('CURRENT_CHECK_INTEGRITY_GAP','Incomplete owner check record')
    content={k:v for k,v in record.items() if k!='id'}
    if record_id('owner-current-check-v2',content)!=record.get('id') or record.get('policy_version')!=POLICY:raise Blocked('CURRENT_CHECK_INTEGRITY_GAP','Owner check record was edited or has unknown policy')
    if aware(record['ingested_at'])>aware(clock) or record['assessment'].get('status')!='usable':raise Blocked('CURRENT_CHECK_INCOMPLETE','Invalid original intake cannot become valid merely as time passes')
    result=assess(record['data'],company,evidence,clock)
    if result['gaps']:raise Blocked('CURRENT_CHECK_BLOCKED',json.dumps(result['gaps']))
    return result

def latest(directory,ticker):
    values=[]
    for p in Path(directory).glob('*.json'):
        try:r=json.loads(p.read_text())
        except (ValueError,OSError) as exc:raise Blocked('CURRENT_CHECK_FILE_INVALID',type(exc).__name__) from exc
        if not isinstance(r,dict) or r.get('policy_version')!=POLICY or not isinstance(r.get('data'),dict):raise Blocked('CURRENT_CHECK_FILE_INVALID','Use intake-generated current-check records, not raw forms')
        if r.get('data',{}).get('company')==ticker:values.append(r)
    return max(values,key=lambda r:(aware(r['ingested_at']),r.get('assessment',{}).get('status')!='usable',r['id'])) if values else None

def owner_pair(record,company,target,evidence,*,clock=None,sec_check=None):
    from .live import verify_durable,sec_publication_check
    evidence=verify_durable(company,evidence)
    check=validate_record(record,company,evidence,clock or now());data=record['data']
    sec=(sec_check or sec_publication_check)(company,target)
    after=aware(clock or now())
    if not sec.get('success') or sec.get('status')!='clear' or not sec.get('checked_at') or not timedelta(0)<=after-aware(sec['checked_at'])<=timedelta(minutes=10):
        raise Blocked('PUBLICATION_CHECK_BLOCKED','Independent fresh SEC check failed or has possible results: '+json.dumps(sec,sort_keys=True))
    # Owner check may expire while SEC is fetched; reassess before returning.
    check=validate_record(record,company,evidence,after)
    schedule={'policy_version':POLICY,'method':'owner_browser','status':'unchanged','checked_at':check['checked_at'],
        'company':company['ticker'],'target_start':target['start'],'target_end':target['end'],
        'source_url':evidence['source_url'],'observed_schedule':data['schedule'],
        'verification_status':'user_verified','owner_check_id':record['id'],'owner_record':record}
    publication={'policy_version':POLICY,'checked_at':min(aware(check['checked_at']),aware(sec['checked_at'])).isoformat(),
        'target_start':target['start'],'target_end':target['end'],'status':'not_observed','sec':sec,
        'official_ir':{'success':True,'checked_at':check['checked_at'],'method':'owner_browser','verification_status':'user_verified','owner_check_id':record['id'],'owner_record':record}}
    return {**evidence,'prelock_schedule_check':schedule},publication

def directory_checker(directory):
    def check(company,target,evidence):
        from .live import refresh_announcement,publication_check
        record=latest(directory,company['ticker'])
        if record is not None:return owner_pair(record,company,target,evidence)
        return refresh_announcement(company,evidence),publication_check(company,target)
    return check

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--directory',type=Path,default=DIRECTORY);a=p.parse_args()
    r=intake(a.input,directory=a.directory)
    print(dumps({'id':r['id'],'record':str(a.directory/(r['id']+'.json')),'ingested_at':r['ingested_at'],'assessment':r['assessment'],'live_prediction_created':False}))
