from copy import deepcopy
from decimal import Decimal as D
import pytest
import psycopg
from earnings import baseline,smoothed_baseline as smooth,live
from earnings.actuals import Blocked
from test_live_baseline import rows,NOW,locked

def test_zero_counts_prior_and_exact_sum():
    p=smooth.rates(dict(below=0,within=0,above=0))
    assert p['below']==D('0.333333333333333333333333') and sum(p.values())==1
    with pytest.raises(Blocked):smooth.probabilities('TEST',[],NOW)

def test_all_above_and_same_selected_inputs():
    r=rows()
    for x in r:x['outcome']='above'
    old=baseline.probabilities('TEST',r,NOW);saved=deepcopy(old)
    new=smooth.from_empirical(old)
    assert old==saved and old['probabilities']['above']==1
    assert new['counts']==old['counts'] and new['historical_ids']==old['historical_ids']
    assert new['probabilities']['below']==D('0.090909090909090909090909')
    assert sum(new['probabilities'].values())==1 and all(0<v<1 for v in new['probabilities'].values())

def test_pool_and_no_future_selection_changes():
    r=rows()+rows('SECOND');new=smooth.probabilities('OTHER',r,NOW);old=baseline.probabilities('OTHER',r,NOW)
    assert new['mode']=='pooled' and new['sample_size']==16
    assert new['historical_ids']==old['historical_ids'] and new['probabilities']==smooth.rates(old['counts'])
    future=deepcopy(r[0]);future.update(id='future',recorded_at='2026-11-14T00:00:00+00:00')
    assert smooth.probabilities('OTHER',r+[future],NOW)==new

@pytest.mark.parametrize('counts',[dict(below=-1,within=0,above=1),dict(below=D(1),within=0,above=0),dict(below=1,within=0)])
def test_bad_counts_rejected(counts):
    with pytest.raises(ValueError):smooth.rates(counts)

def test_db_laplace_guard_and_parallel_duplicate_protection(locked):
    conn,g,b,e,check,target,empirical=locked;new=smooth.from_empirical(b)
    saved=live.insert_prediction(conn,{'ticker':'TEST'},target,g,new,e,check)
    assert saved['id']!=empirical['id']
    assert live.insert_prediction(conn,{'ticker':'TEST'},target,g,new,e,check) is None
    forged={**new,'probabilities':{'below':D('.5'),'within':D('.25'),'above':D('.25')}}
    with pytest.raises(psycopg.Error,match='Laplace historical counts'):
        with conn.transaction():live.insert_prediction(conn,{'ticker':'TEST'},target,g,forged,e,check)

def test_partial_pair_does_not_silently_change_input_cutoff(locked,monkeypatch):
    from earnings import predict
    from test_core import COMPANY
    conn,g,b,e,check,target,saved=locked
    c={**COMPANY,'quarter_targets':[target],'next_report':{}}
    monkeypatch.setattr(predict.history,'ingest',lambda conn:{'inserted':0})
    monkeypatch.setattr(predict.history,'stored',lambda conn:[])
    result=predict.run(conn,{'TEST':c},methods=(baseline.METHOD,smooth.METHOD))
    assert not result['locked'] and result['skipped'][0]['code']=='PARTIAL_METHOD_PAIR_REVIEW'
