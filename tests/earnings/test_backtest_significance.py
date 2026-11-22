from decimal import Decimal
import json
from pathlib import Path
import pytest

from earnings.backtest_significance import paired_company_bootstrap, percentile, sentence, SMOOTHED, POOLED


def row(id_, company, smoothed, pooled, mode='company'):
    return {'id':id_,'company':company,'selection':{'mode':mode},'brier':{SMOOTHED:smoothed,POOLED:pooled}}


def test_whole_paired_company_clusters_and_per_prediction_denominator(monkeypatch):
    class FixedDraws:
        def __init__(self,seed):self.indices=iter([0,0,1,1])
        def randrange(self,n):
            assert n==2
            return next(self.indices)
    monkeypatch.setattr('earnings.backtest_significance.random.Random',FixedDraws)
    rows=[row('a1','A','0.8','1'),row('a2','A','0.6','1'),row('b','B','1.3','1'),row('ignored','C','0','2',mode='pooled')]
    result=paired_company_bootstrap(rows,resamples=2,seed=123)
    assert result['n_predictions']==3 and result['n_companies']==2
    assert result['company_sizes']=={'A':2,'B':1}
    assert result['mean_difference']==Decimal('-0.1')
    assert result['interval']=={'low':Decimal('-0.285'),'high':Decimal('0.285')}
    assert result['resampled_quarter_count_range']==[2,4]
    assert not result['excludes_zero']
    assert 'includes zero' in sentence(result)


def test_reproducible_independent_of_input_order_and_only_own_subset():
    rows=[row('a','A','0.1','0.3'),row('b','B','0.2','0.4')]
    a=paired_company_bootstrap(rows,seed=3,resamples=100)
    b=paired_company_bootstrap(list(reversed(rows)),seed=3,resamples=100)
    assert a==b and a['interval']=={'low':Decimal('-0.2'),'high':Decimal('-0.2')}
    assert a['excludes_zero'] and 'in favor of Smoothed' in sentence(a)
    assert a==paired_company_bootstrap(rows+[row('c','C','2','0',mode='pooled')],seed=3,resamples=100)


def test_percentiles_and_invalid_inputs():
    assert percentile([Decimal('-1'),Decimal('1')],Decimal('0.025'))==Decimal('-0.95')
    assert percentile([Decimal('-1'),Decimal('1')],Decimal('0.975'))==Decimal('0.95')
    for rows in ([],[row('a','A','0','1')],[row('a','A','0','1'),row('a','B','0','1')],[row('a','A','NaN','1'),row('b','B','0','1')]):
        with pytest.raises(ValueError):paired_company_bootstrap(rows,resamples=2)
    with pytest.raises(ValueError):paired_company_bootstrap([],resamples=1)


def test_saved_10000_resamples_reproduce_and_preserve_score_difference():
    root=Path(__file__).resolve().parents[2]
    d=json.loads((root/'earnings/reports/backtest_walkforward.json').read_text())
    calculated=paired_company_bootstrap(d['evaluated'])
    saved=d['company_cluster_bootstrap']
    # JSON serializes Decimals as exact strings, with all other metadata intact.
    from earnings.models import dumps
    assert json.loads(dumps(calculated))==saved
    assert calculated['n_predictions']==108 and calculated['n_companies']==64
    assert calculated['resamples']==10000 and calculated['seed']==20261121
    assert abs(calculated['mean_difference']-(Decimal(d['by_history_mode']['company']['mean_brier'][SMOOTHED])-Decimal(d['by_history_mode']['company']['mean_brier'][POOLED])))<Decimal('1e-26')
    pub=json.loads((root/'earnings/publication/backtest.json').read_text())
    assert pub['company_cluster_bootstrap']==saved
    assert pub['company_cluster_bootstrap_sentence']==sentence(saved)
