"""Record user-supplied results-release timing without inventing verification.

No records are published to the registry automatically. Entry time is generated
on receipt, never accepted from the input or used as a historical issue date.
"""
import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .dates import IR_HOSTS
from .models import record_id, dumps

REQUIRED={'company','supplied_by','source_url','release_date','timezone','time_precision','release_time'}


def confirmation(data):
    if set(data) != REQUIRED:
        raise ValueError('Supply exactly company, supplied_by, source_url, release_date, timezone, time_precision, release_time; entry/verification timestamps cannot be supplied')
    ticker=data['company'].upper()
    if ticker not in IR_HOSTS or not isinstance(data['supplied_by'],str) or not data['supplied_by'].strip():
        raise ValueError('Supported company and named supplier required')
    u=urlparse(data['source_url'])
    if u.scheme!='https' or u.hostname not in IR_HOSTS[ticker] or u.username or u.password or u.port:
        raise ValueError('Use an official company IR URL for announcement evidence')
    date.fromisoformat(data['release_date'])
    precision=data['time_precision'];value=data['release_time'];zone=data['timezone']
    if precision not in ('date','hour','minute','second','market_session'):
        raise ValueError('Unknown time precision')
    if zone is not None:
        try:ZoneInfo(zone)
        except ZoneInfoNotFoundError as exc:raise ValueError('Use an IANA timezone or explicit null when unknown') from exc
    if precision=='date':
        if value is not None:raise ValueError('Date-only precision requires null release_time')
    elif precision=='market_session':
        if zone is None or value not in ('before_market_open','after_market_close','during_market_hours'):
            raise ValueError('Market session requires an explicit timezone and session')
    else:
        if zone is None or not isinstance(value,str):raise ValueError('Clock time requires an explicit timezone')
        fmt={'hour':'%H','minute':'%H:%M','second':'%H:%M:%S'}[precision]
        parsed=datetime.strptime(value,fmt)
        if parsed.strftime(fmt)!=value:raise ValueError('Clock text must match its stated precision')
    result={**data,'company':ticker,'event_kind':'results_release','verification_status':'user_verified',
            'independently_checked':False,'entered_at':datetime.now(timezone.utc).isoformat(),
            'announcement_issued_at':None,'note':'User-supplied timing, not independently checked. Entry time is not announcement publication time.'}
    result['id']=record_id('manual-results-release-confirmation-v1',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Append a user-verified results-release timing observation; no registry publication')
    parser.add_argument('input',type=Path)
    parser.add_argument('--output',type=Path,default=Path('data/cache/earnings/manual-date-confirmations.jsonl'))
    args=parser.parse_args();result=confirmation(json.loads(args.input.read_text()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('a') as stream:stream.write(json.dumps(result,sort_keys=True)+'\n')
    print(dumps(result))
