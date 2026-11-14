from copy import deepcopy
from pathlib import Path
import pytest
from pypdf import PdfWriter
from pypdf.generic import NameObject,DictionaryObject,DecodedStreamObject
from earnings import owner_evidence as owner
from earnings.live import deadline
from earnings.actuals import Blocked

def pdf(path,text):
    w=PdfWriter();page=w.add_blank_page(width=600,height=800)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):w._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(('BT /F1 10 Tf 10 700 Td ('+text+') Tj ET').encode())
    page[NameObject('/Contents')]=w._add_object(stream)
    with path.open('wb') as f:w.write(f)

TEXT='CrowdStrike November 4, 2026 Third Quarter fiscal 2027. CrowdStrike will announce financial results on December 1, 2026 after the U.S. market close.'
def setup(tmp_path):
    p=tmp_path/'source.pdf';pdf(p,TEXT);root=tmp_path/'cache'
    m=dict(company='CRWD',supplied_by='Owner synthetic test',source_url='https://ir.crowdstrike.com/press-releases/test',owner_retrieved_at='2026-11-13T01:00:00-08:00')
    i=owner.ingest(p,m,root=root)
    r=dict(announcement_issued_date='2026-11-04',release_date='2026-12-01',release_time='after_market_close',time_precision='market_session',timezone='America/New_York',timezone_provenance='Owner-supplied US market context, synthetic',reviewed_by='Codex synthetic review',review_note='Synthetic full-document review',quotes=dict(company='CrowdStrike',fiscal_period='Third Quarter fiscal 2027',announcement_date='November 4, 2026',release_date='December 1, 2026',results_publication='CrowdStrike will announce financial results on December 1, 2026 after the U.S. market close.',release_time='after the U.S. market close'))
    return p,root,i,r

def test_intake_integrity_provenance_review_and_append(tmp_path):
    p,root,i,r=setup(tmp_path);e=owner.review(i['id'],r,root=root)
    assert Path(i['preserved_file']).read_bytes()==p.read_bytes() and not e['gaps']
    assert e['verification_status']=='user_verified' and not e['independently_checked']
    assert e['owner_retrieved_at']=='2026-11-13T01:00:00-08:00' and e['ingested_at']!=e['owner_retrieved_at']
    assert deadline(e).isoformat()=='2026-12-01T05:00:00+00:00'
    folder=tmp_path/'announcements';folder.mkdir();(folder/'CRWD.json').write_text('{"company":"CRWD","versions":[{"id":"old-403","http_status":403}]}')
    owner.append(e,directory=folder);owner.append(e,directory=folder)
    import json
    data=json.loads((folder/'CRWD.json').read_text());assert len(data['versions'])==2 and data['versions'][0]['http_status']==403
    refreshed=owner.refresh({'ticker':'CRWD'},e,root=root)
    assert refreshed['checked_at']!=e['checked_at'] and refreshed['owner_retrieved_at']==e['owner_retrieved_at']
    assert refreshed['recheck']['kind']=='local_owner_file_integrity_check_not_HTTP_refresh'
    Path(i['preserved_file']).write_bytes(b'changed')
    with pytest.raises(Blocked):owner.refresh({'ticker':'CRWD'},e,root=root)

def test_call_only_or_wrong_date_cannot_be_promoted(tmp_path):
    p,root,i,r=setup(tmp_path);r['release_date']='2026-12-02';r['quotes']['results_publication']='Third Quarter fiscal 2027'
    e=owner.review(i['id'],r,root=root)
    assert e['verification_status']=='unverified' and 'RESULTS_PUBLICATION_WORDING_NOT_ESTABLISHED' in e['gaps']
    with pytest.raises(ValueError):owner.append(e,directory=tmp_path/'announcements')

def test_no_supplied_ingestion_or_verification_timestamp(tmp_path):
    p,root,i,r=setup(tmp_path);r['verified_at']='2026-11-01T00:00:00Z'
    with pytest.raises(ValueError):owner.review(i['id'],r,root=root)
