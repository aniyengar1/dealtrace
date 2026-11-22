"""Read-only date-source observations. IR exception is dates-only and allowlisted.

No previous fetch timestamps are inferred. A failed request has checked_at but
no fetched_at. These observations do not silently change confirmed dates.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from src.fetch import USER_AGENT
from .sec import fetch as sec_fetch, CACHE

IR_HOSTS = {
    'PD': {'investor.pagerduty.com'}, 'GTLB': {'ir.gitlab.com'},
    'CRM': {'investor.salesforce.com'}, 'CRWD': {'ir.crowdstrike.com'},
    'OKTA': {'investor.okta.com'}, 'IOT': {'investors.samsara.com'},
    'MDB': {'investors.mongodb.com'}, 'S': {'investors.sentinelone.com'},
    'ADBE': {'www.adobe.com'}, 'LULU': {'corporate.lululemon.com'},
}


def check_source(ticker, url, *, source_date, report_date=None, cache=CACHE):
    parsed=urlparse(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port:
        raise ValueError('Date sources require plain HTTPS URLs')
    sec = parsed.hostname in {'www.sec.gov','sec.gov','data.sec.gov'}
    if not sec and parsed.hostname not in IR_HOSTS[ticker]:
        raise ValueError('Date-only IR source is outside company allowlist')
    observation={'company':ticker,'source_url':url,'source_date':source_date,
                 'report_date':report_date,'checked_at':datetime.now(timezone.utc).isoformat(),
                 'fetched_at':None,'status':'unverified','sha256':None}
    try:
        if sec:
            body,manifest=sec_fetch(url,refresh=True,cache=cache)
            observation.update(fetched_at=manifest['fetched_at'],sha256=manifest['sha256'])
        else:
            # Do not follow redirects onto an unauthorized domain.
            response=requests.get(url,headers={'User-Agent':USER_AGENT},timeout=30,allow_redirects=False)
            if response.status_code != 200:
                observation['http_status']=response.status_code
                return observation
            body=response.content
            observation.update(fetched_at=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(body).hexdigest())
            directory=cache/'ir-dates';directory.mkdir(parents=True,exist_ok=True)
            key=hashlib.sha256(url.encode()).hexdigest()
            (directory/f'{key}-{observation["sha256"]}.body').write_bytes(body)
        text=' '.join(BeautifulSoup(body,'html.parser').get_text(' ',strip=True).split())
        def written(day):
            from datetime import date
            d=date.fromisoformat(day)
            return (f'{d:%B} {d.day}, {d.year}',f'{d:%B} {d.day} {d.year}',
                    f'{d:%b} {d.day}, {d.year}', f'{d:%b}. {d.day}, {d.year}',day)
        issue=any(v in text for v in written(source_date))
        report=bool(report_date) and any(v in text for v in written(report_date))
        observation.update(source_date_present=issue,report_date_present=report,
                           status='confirmed' if issue and report else 'retrieved_unverified')
        # Excerpts are inspection aids, not automatic date interpretation.
        observation['date_evidence']=[text[max(0,text.find(v)-60):text.find(v)+len(v)+90]
                                     for v in written(report_date or source_date) if v in text][:1]
    except (requests.RequestException, RuntimeError, OSError) as exc:
        observation['error_type']=type(exc).__name__
    return observation


def check_registry(registry):
    results=[]
    for ticker,company in registry.items():
        for purpose in ('next_report','annual_result'):
            source=company[purpose]
            result=check_source(ticker,source['source_url'],source_date=source['source_date'],report_date=source.get('date'))
            result['purpose']=purpose
            results.append(result)
    return results


if __name__ == '__main__':
    from .models import dumps
    from .registry import companies
    print(dumps(check_registry(companies())))
