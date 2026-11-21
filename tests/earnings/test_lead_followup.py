import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_financial_backtest_inputs_remain_pinned():
    financial=ROOT/'earnings/reports/scaling_lock_readiness_2027Q1.json'
    backtest=json.loads((ROOT/'earnings/reports/backtest_walkforward.json').read_text())
    follow=json.loads((ROOT/'earnings/reports/lead_time_followup_2026-11-20.json').read_text())
    assert hashlib.sha256(financial.read_bytes()).hexdigest()==backtest['source_hashes']['scaling_audit_sha256']==follow['financial_audit_sha256']


def test_four_matching_pairs_required_and_schedule_mismatch_preserved():
    x=json.loads((ROOT/'earnings/reports/lead_time_followup_2026-11-20.json').read_text())
    assert x['complete_count']==24 and len(x['new_complete'])==13 and x['remaining_count']==40
    for c in x['companies']:
        assert c['complete']==(c['verified_matching_pairs']==4)
        assert (c['typical_gap_days'] is not None)==c['complete']
    lite=next(c for c in x['companies'] if c['ticker']=='LITE')
    assert lite['verified_matching_pairs']==3 and lite['schedule_mismatches'][0]['scheduled_release']=='2026-11-05'
    assert '2026-11-02' in lite['missing_regular_release_dates']


def test_regular_release_lead_does_not_clear_preliminary_publication_blocks():
    x=json.loads((ROOT/'earnings/reports/lead_time_followup_2026-11-20.json').read_text())
    for t,d in [('DOCN','2026-08-04'),('ONTO','2026-05-05')]:
        c=next(c for c in x['companies'] if c['ticker']==t)
        assert next(p for p in c['pairs'] if p['scheduled_release']==d)['completed_period_disclosure_blocks']
