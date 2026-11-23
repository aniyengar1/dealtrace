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


def test_default_generator_reads_its_input_not_a_separately_prepared_seed():
    # A committed seed may come from a newer explicit reviewed export. It must
    # not be required to match the older default source JSON byte-for-byte.
    import re
    payloads=re.findall(r"VALUES \('current',(\$snapshot_[0-9a-f]+\$)(.*?)\1::jsonb\)",script(),re.S)
    assert len(payloads)==2
    assert json.loads(payloads[0][1])==json.loads((ROOT/'predictions.json').read_text())
    assert json.loads(payloads[1][1])==json.loads((ROOT/'backtest.json').read_text())


def test_prepared_seed_has_consistent_public_counts_and_no_private_evidence():
    import re
    sql=(ROOT/'published_snapshot_seed.sql').read_text()
    values=re.findall(r"VALUES \('current',(\$snapshot_[0-9a-f]+\$)(.*?)\1::jsonb\)",sql,re.S)
    assert len(values)==2
    p=json.loads(values[0][1]);rows=p['predictions']
    assert p['prediction_count']==len(rows)==len({r['id'] for r in rows})
    assert len(p['ledger_sha256'])==64
    assert all(sum(x['company']==r['company'] for x in rows)==2 for r in rows)
    for private in ['owner_record','owner_check_id','observer','attestation','personally_checked','cached_body','data/cache/','/Users/','/tmp/']:
        assert private not in sql
