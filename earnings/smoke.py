"""Read-only HTTP checks of the running Next.js interface. No browser automation."""
import argparse
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from .models import dumps
from .registry import companies


def check(base):
    parsed=urlparse(base)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.username or parsed.password:
        raise ValueError('Smoke checks only target a local HTTP application')
    def get(path):
        r=requests.get(base.rstrip('/')+path,timeout=20)
        return r,BeautifulSoup(r.text,'html.parser').get_text(' ',strip=True)
    checks=[]
    for ticker,company in companies().items():
        expected = 'blocked' if company.get('comparability', {}).get('blocked') else 'experimental'
        response=requests.get(f'{base}/api/crosscheck/{ticker}?asOf=2026-11-11',timeout=20)
        response.raise_for_status();report=response.json()
        assert report['forecast']['status']==expected
        page,text=get(f'/crosscheck/{ticker}?asOf=2026-11-11')
        assert page.status_code==200 and report['company']['name'] in text
        assert ('Forecast withheld' if expected=='blocked' else report['forecast_display']['estimate']) in text
        assert 'Guidance history' in text and 'Evidence' in text
        assert report['forecast']['probabilities'] is None and report['forecast']['interval'] is None
        assert all(source['filed']<='2026-11-11' for source in report['selected_inputs'].values())
        checks.append({'company':ticker,'status':expected,'report_id':report['id'],'estimate':report['forecast_display']['estimate']})
    index,text=get('/crosscheck');assert index.status_code==200 and 'PagerDuty' in text and 'GitLab' in text
    unsupported,text=get('/crosscheck/MSFT');assert 'This company is not supported yet.' in text
    assert requests.get(base+'/api/crosscheck/MSFT',timeout=20).status_code==404
    _,text=get('/crosscheck/PD?asOf=2026-11-12');assert 'No published report' in text
    _,text=get('/crosscheck/PD?asOf=wrong');assert 'Invalid as-of date' in text
    assert requests.get(base+'/api/crosscheck/PD?asOf=wrong',timeout=20).status_code==400
    return {'checks':checks,'unsupported':'MSFT explicitly unsupported','missing_cutoff':'no substituted report','invalid_date':'rejected','verification':'Direct HTTP and server-rendered HTML; no browser automation'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:3011');args=p.parse_args()
    print(dumps(check(args.base_url)))
