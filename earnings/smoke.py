"""Read-only HTTP checks of the running Next.js interface. No browser automation."""
import argparse
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from .models import dumps
from .registry import companies


def check(base, experimental_forecast=False):
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
        if experimental_forecast:
            assert report['forecast']['status']==expected
        else:
            assert not {'forecast','forecast_display','evaluation','evaluation_display'}.intersection(report)
        page,text=get(f'/crosscheck/{ticker}?asOf=2026-11-11')
        assert page.status_code==200 and report['company']['name'] in text
        if experimental_forecast:
            assert ('Forecast withheld' if expected=='blocked' else report['forecast_display']['estimate']) in text
        else:
            assert 'Annual revenue forecast' not in text and 'Historical evaluation' not in text
            assert 'Quarterly guidance-implied growth' in text
            assert report['quarterly'] is not None
            quarter=report['quarterly']
            if not quarter['codes']:
                assert quarter['display']['growth_low'] in text and quarter['display']['growth_high'] in text
                assert quarter['comparison']['id'] in text
                assert quarter['guidance']['source_url'] in page.text and quarter['comparison']['source_url'] in page.text
            assert ('INCOMPARABLE_BASIS' in report['quarterly']['codes']) == (expected=='blocked')
        assert 'Guidance history' in text and 'Evidence' in text
        if experimental_forecast:
            assert report['forecast']['probabilities'] is None and report['forecast']['interval'] is None
        assert all(source['filed']<='2026-11-11' for source in report['selected_inputs'].values())
        checks.append({'company':ticker,'status':expected if experimental_forecast else ('blocked' if expected=='blocked' else 'ok'),'report_id':report['id'],'experimental_forecast_visible':experimental_forecast,'quarterly_visible':report.get('quarterly') is not None})
    index,text=get('/crosscheck');assert index.status_code==200 and 'PagerDuty' in text and 'GitLab' in text
    unsupported,text=get('/crosscheck/MSFT');assert 'This company is not supported yet.' in text
    assert requests.get(base+'/api/crosscheck/MSFT',timeout=20).status_code==404
    _,text=get('/crosscheck/PD?asOf=2026-11-12');assert 'No published report' in text
    _,text=get('/crosscheck/PD?asOf=wrong');assert 'Invalid as-of date' in text
    assert requests.get(base+'/api/crosscheck/PD?asOf=wrong',timeout=20).status_code==400
    return {'checks':checks,'unsupported':'MSFT explicitly unsupported','missing_cutoff':'no substituted report','invalid_date':'rejected','verification':'Direct HTTP and server-rendered HTML; no browser automation'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='http://127.0.0.1:3011');p.add_argument('--experimental-forecast',action='store_true');args=p.parse_args()
    print(dumps(check(args.base_url,args.experimental_forecast)))
