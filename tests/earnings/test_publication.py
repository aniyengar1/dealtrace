from copy import deepcopy
from pathlib import Path
from decimal import Decimal
import json,sqlite3
import pytest
from earnings.publication.export import archive,read_copy,public_view
from earnings.models import digest

SNAPSHOT=Path('earnings/publication/predictions.json')

def data():
    # Synthetic private-row fixtures reconstructed from the committed public copy;
    # unit tests never require ignored caches or connect to a source database.
    public=json.loads(SNAPSHOT.read_text());predictions=[]
    for r in public['predictions']:
        g={**r['guidance'],'company':r['company'],'start':r['period_start'],'end':r['period_end']}
        predictions.append({'id':r['id'],'ticker':r['company'],'name':r['name'],'metric':'quarterly_consolidated_revenue','period_start':r['period_start'],'period_end':r['period_end'],'guidance_id':g['id'],'method_version':r['method'],'made_at':r['locked_at'],'snapshot':{'locked_guidance':g,'latest_registry_target':{'label':r['quarter']},'baseline':{'sample_size':r['sample_size'],'historical_ids':['synthetic-unit-input']}},'announcement':r['announcement'],'publication_check':{'fixture':'not live'},**{'p_'+k:v for k,v in r['probabilities'].items()}})
    content={'predictions':sorted(predictions,key=lambda p:p['id']),'results':[],'historical_observations':[]}
    return {'schema_version':'crosscheck-ledger-copy-v1','exported_at':public['copied_at'],'content_sha256':digest(content),'ledger_sha256':digest({'predictions':content['predictions'],'results':[]}),**content}


def test_current_copy_has_exact_eight_locks_and_no_outcomes():
    d=data();p=public_view(d)
    assert len(p['predictions'])==8 and {r['company'] for r in p['predictions']}=={'OKTA','CRM','IOT','S'}
    assert all(r['result'] is None for r in p['predictions'])
    assert len({r['id'] for r in p['predictions']})==8
    for r in p['predictions']:
        assert sum(Decimal(x) for x in r['probabilities'].values())==1
        assert len(r['evidence_sha256'])==64
    serialized=json.dumps(p)
    assert 'owner_record' not in serialized and 'Anirudh' not in serialized and 'personally_checked' not in serialized


def test_copy_corruption_rejected_and_archives_never_overwritten(tmp_path):
    d=data();p=tmp_path/'copy.sqlite3';archive(d,p)
    assert read_copy(p)['content_sha256']==d['content_sha256']
    with pytest.raises(FileExistsError):archive(d,p)
    with sqlite3.connect(p) as c:c.execute("UPDATE predictions SET payload='{}' WHERE id=(SELECT min(id) FROM predictions)")
    with pytest.raises(ValueError,match='integrity'):read_copy(p)


def test_corrections_select_latest_without_erasing_history():
    d=deepcopy(data());p=d['predictions'][0];g=p['snapshot']['locked_guidance']
    def score(id,at,amount,parent=None):
        return dict(id=id,prediction_id=p['id'],status='scored',outcome='within',brier='0.5',scored_at=at,evidence_hash=id,supersedes_id=parent,
            snapshot={'review':{'actual':{'value':amount,'unit':'USD','start':g['start'],'end':g['end'],'accession':'result-accession','filed':'2026-12-04'},'result_source':{'url':'https://www.sec.gov/Archives/fixture-result'}}})
    d['results']=[score('first','2026-12-05T00:00:00Z',g['low']),score('correction','2026-12-06T00:00:00Z',g['high'],'first')]
    r=next(x for x in public_view(d)['predictions'] if x['id']==p['id'])
    assert r['score_versions']==2 and r['result']['id']=='correction' and r['result']['actual']['value']==format(Decimal(g['high']),'f')
    assert len(d['results'])==2


def test_hash_includes_every_locked_input_and_not_only_quote():
    d=data();before=public_view(d)['predictions'];changed=deepcopy(d)
    p=changed['predictions'][0];p['snapshot']['baseline']['historical_ids']=['different-input']
    after={r['id']:r for r in public_view(changed)['predictions']}
    original=next(r for r in before if r['id']==p['id'])
    assert original['evidence_sha256']!=after[p['id']]['evidence_sha256']
