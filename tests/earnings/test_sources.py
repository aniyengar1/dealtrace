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
