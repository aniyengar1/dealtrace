import json,hashlib
from pathlib import Path
from urllib.parse import urlparse
from earnings.research.lead_time_progress import build,ROOT
from earnings.research.scaling_2027q1_dates import HOSTS


def test_two_complete_studies_added_without_relaxing_four_pair_requirement():
    r=build();assert r['complete_count']==26 and r['remaining_count']==38
    assert set(r['new_complete'])=={'CNXC','KFRC'}
    for c in r['companies']:
        assert c['complete']==(c['verified_matching_pairs']==4)
        assert bool(c['typical_gap_days'])==c['complete']
    c={x['ticker']:x for x in r['companies']}
    assert c['CNXC']['typical_gap_days']=='20' and c['KFRC']['typical_gap_days']=='23'
    assert c['ICHR']['verified_matching_pairs']==1 and c['LITE']['verified_matching_pairs']==3
    for t in ['APPN','TENB','FIVN']:assert c[t]['verified_matching_pairs']==1


def test_all_additions_are_official_dated_and_match_pinned_sec_results():
    r=build();assert len(r['new_pairs'])==6
    financial=ROOT/'reports/scaling_lock_readiness_2027Q1.json'
    assert hashlib.sha256(financial.read_bytes()).hexdigest()==r['financial_audit_sha256']
    for p in r['new_pairs']:
        assert urlparse(p['url']).hostname==HOSTS[p['ticker']]
        assert p['issued']<p['scheduled_release']==p['matched_sec_result']['report_date']
        assert 'release' in p['quote'] and p['issuance_date_quote']
        assert len(p['artifact_sha256'])==64 and p['retrieved_at']
    global_pairs=json.loads((ROOT/'research/scaling_2027q1/announcement_pairs.json').read_text())['pairs']
    assert global_pairs[-6:]==r['new_pairs']
    prior=json.loads((ROOT/'reports/lead_time_followup_2026-11-20.json').read_text())
    assert prior['complete_count']==24 and prior['remaining_count']==40
