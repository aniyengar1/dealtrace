"""No live locking: fixed-input regression files and read-only DB evidence."""
from pathlib import Path
import json,subprocess

ROOT=Path(__file__).resolve().parents[2]

def test_tag_target_protected_files_and_fixed_regression():
    report=json.loads((ROOT/'earnings/validation/session4_lock_regression_summary.json').read_text())
    assert subprocess.check_output(['git','rev-parse','session3-lock-ready^{}'],cwd=ROOT,text=True).strip()==report['tag_commit']
    assert report['all_protected_files_unchanged'] and report['dependency_freeze_unchanged']
    a=json.loads((ROOT/'earnings/validation/session4_lock_regression_tag.json').read_text());b=json.loads((ROOT/'earnings/validation/session4_lock_regression_head.json').read_text())
    assert a==b and not a['database_access'] and not a['ledger_writes_possible']
    assert {c['case'] for c in a['cases']}=={'outside','inside','deadline','withdrawn','stale_actual','already_public','missing_history'}
    inside=next(c for c in a['cases'] if c['case']=='inside')
    assert {c['company'] for c in inside['eligible_candidates']}=={'CRM','OKTA','IOT','S'}
    for candidate in inside['eligible_candidates']:
        assert candidate['guidance_id'] and candidate['historical_input_ids'] and candidate['probabilities']


def test_actual_clock_dry_runs_readonly_and_no_ledger_changes():
    for version in ['tag','head']:
        result=json.loads((ROOT/f'earnings/validation/session4_lock_dry_run_{version}.json').read_text())
        assert result['transaction_read_only']=='on' and result['ledger_writes_possible'] is False
        assert result['ledger_count_after']==result['ledger_count_before']==0 and not result['locked']
        assert result['schema_compatible'] and not result['unimported_history_ids']
