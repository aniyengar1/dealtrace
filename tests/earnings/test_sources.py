from datetime import date
import json
from types import SimpleNamespace
import pytest
from earnings.sec import fetch
from earnings import sec
from earnings.__main__ import reporting_asof
from earnings.registry import companies


def test_sec_transport_cache_and_revision_integrity(tmp_path,monkeypatch):
    calls=[]
    def get(url,**kwargs):
        calls.append((url,kwargs));return SimpleNamespace(content=f'version-{len(calls)}'.encode())
    monkeypatch.setattr(sec.transport,'_throttled_get',get)
    u='https://data.sec.gov/submissions/CIK0000000001.json'
    first,m1=fetch(u,cache=tmp_path);assert fetch(u,cache=tmp_path)[0]==first and len(calls)==1
    second,m2=fetch(u,cache=tmp_path,refresh=True)
    assert first!=second and (tmp_path/m1['body']).exists() and (tmp_path/m2['body']).exists()
    (tmp_path/m2['body']).write_bytes(b'tampered')
    with pytest.raises(ValueError,match='integrity'):fetch(u,cache=tmp_path)
    assert calls[0][1]['allow_redirects'] is False


@pytest.mark.parametrize('url',['https://example.com/','https://www.sec.gov.evil.test/','http://sec.gov/','https://user@sec.gov/','https://sec.gov:444/'])
def test_source_restrictions(url,tmp_path):
    with pytest.raises(ValueError):fetch(url,cache=tmp_path)


def test_announcement_not_visible_before_publication():
    c=companies()['CRM']
    assert reporting_asof(c,date(2026,11,9))['next_report']['date'] is None
    assert reporting_asof(c,date(2026,11,10))['next_report']['date']=='2026-12-02'


def test_ir_date_check_records_real_fetch_and_rejects_redirect(tmp_path,monkeypatch):
    from earnings import dates
    url='https://investor.salesforce.com/announcement'
    calls=[]
    def get(url,**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(status_code=200,content=b'November 10, 2026: earnings on December 2, 2026')
    monkeypatch.setattr(dates.requests,'get',get)
    r=dates.check_source('CRM',url,source_date='2026-11-10',report_date='2026-12-02',cache=tmp_path)
    assert r['status']=='confirmed' and r['fetched_at'] and r['checked_at'] and r['sha256']
    assert calls[0]['allow_redirects'] is False
    monkeypatch.setattr(dates.requests,'get',lambda *a,**k:SimpleNamespace(status_code=302))
    r=dates.check_source('CRM',url,source_date='2026-11-10',report_date='2026-12-02',cache=tmp_path)
    assert r['status']=='unverified' and r['fetched_at'] is None and r['http_status']==302


@pytest.mark.parametrize('url',['https://evil.test/','https://investor.salesforce.com.evil.test/','http://investor.salesforce.com/'])
def test_ir_allowlist_is_company_specific(url,tmp_path):
    from earnings.dates import check_source
    with pytest.raises(ValueError):check_source('CRM',url,source_date='2026-11-10',cache=tmp_path)
    with pytest.raises(ValueError):check_source('PD','https://investor.salesforce.com/',source_date='2026-11-10',cache=tmp_path)


def test_failed_ir_check_does_not_invent_fetch_time(tmp_path,monkeypatch):
    import requests
    from earnings import dates
    def get(*a,**k):raise requests.ConnectionError('offline')
    monkeypatch.setattr(dates.requests,'get',get)
    r=dates.check_source('CRM','https://investor.salesforce.com/date',source_date='2026-11-10',cache=tmp_path)
    assert r['checked_at'] and r['fetched_at'] is None and r['error_type']=='ConnectionError'
