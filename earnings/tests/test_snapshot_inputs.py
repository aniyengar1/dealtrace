"""Tests stay inside earnings/ under the owner's bounded-change instruction."""
import json
from pathlib import Path
import pytest
from earnings.publication.snapshot_sql import script,ROOT


def fixtures(path, *, simulation=False):
    for name in ['predictions.json','backtest.json']:
        payload=json.loads((ROOT/name).read_text())
        payload['test_input_identity']='explicit-isolated-publication-directory'
        if simulation:payload['simulation']=True
        (path/name).write_text(json.dumps(payload))


def test_explicit_source_directory_does_not_seed_the_default_pending_copy(tmp_path):
    fixtures(tmp_path)
    sql=script(tmp_path)
    assert sql.count('explicit-isolated-publication-directory')==2
    assert sql.count('INSERT INTO public.')==2
    assert 'Synthetic seed requires' not in sql


def test_synthetic_payloads_are_rejected_by_production_generator(tmp_path):
    fixtures(tmp_path,simulation=True)
    with pytest.raises(ValueError,match='production'):script(tmp_path)
    sql=script(tmp_path,allow_synthetic=True)
    assert sql.startswith('-- SYNTHETIC SCRATCH REHEARSAL ONLY')
    assert 'current_database()' in sql and 'current_setting(\'data_directory\')' in sql
    assert 'crosscheck_scoring_rehearsal_%' in sql


def test_default_seed_is_unchanged():
    assert script()==(ROOT/'published_snapshot_seed.sql').read_text()
