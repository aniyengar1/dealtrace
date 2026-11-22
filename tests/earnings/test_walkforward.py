from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import json
from pathlib import Path

from earnings import baseline, smoothed_baseline
from earnings.backtest_walkforward import training_rows, evaluate, calibration, load_observations, summary


def row(i, *, outcome='above', end=None, public='2024-01-01T05:00:00+00:00'):
    return {'id':str(i),'company':'X','period_start':f'2024-{i:02}-01','period_end':end or f'2024-{i:02}-28','status':'eligible','outcome':outcome,'public_available_at':public,'recorded_at':'2026-11-20T00:00:00+00:00','release_date':f'2024-{i:02}-29','guidance_id':'guide-'+str(i),'actual_id':'actual-'+str(i),'source_population':'synthetic'}


def fixture():
    rows=[row(i,outcome=['below','within','within','above','above','above'][i-1]) for i in range(1,7)]
    target=row(7);target['release_date']='2024-08-15';target['public_available_at']='2024-08-16T04:00:00+00:00'
    return rows+[target]


def test_frozen_methods_and_hand_worked_brier():
    rows=fixture();cases,_=evaluate(rows);p=next(r for r in cases if r['id']=='7')
    assert p['selection']['counts']=={'below':1,'within':2,'above':3}
    assert p['selection']['mode']=='company'
    with localcontext() as ctx:
        ctx.prec=80
        assert abs(p['brier'][baseline.METHOD]-Decimal(7)/18)<Decimal('1e-23')
        assert abs(p['brier'][smoothed_baseline.METHOD]-Decimal(38)/81)<Decimal('1e-23')
        assert abs(p['brier']['uniform']-Decimal(2)/3)<Decimal('1e-23')
    assert p['brier']['always-above']==0


def test_future_outcome_cannot_change_earlier_prediction():
    rows=fixture();future=row(8,outcome='below',public='2024-10-01T04:00:00+00:00')
    first,_=evaluate(rows+[future]);future['outcome']='above';second,_=evaluate(rows+[future])
    a=next(r for r in first if r['id']=='7');b=next(r for r in second if r['id']=='7')
    assert a==b
    assert '8' not in a['selection']['historical_ids'] and '7' not in a['selection']['historical_ids']


def test_late_sec_filing_and_exact_availability_boundary():
    target=row(7);r=row(1,public='2024-08-01T04:00:00+00:00')
    before=datetime.fromisoformat('2024-08-01T03:59:59.999999+00:00')
    at=datetime.fromisoformat('2024-08-01T04:00:00+00:00')
    assert not training_rows([r],target,before)
    assert training_rows([r],target,at)==[r]
    # A different company's same/later fiscal period is also excluded.
    r['company']='Y';r['period_end']=target['period_end']
    assert not training_rows([r],target,at)


def test_laplace_does_not_bypass_frozen_history_minimum():
    cases,blocked=evaluate(fixture()[:2])
    assert not cases and len(blocked)==2
    assert all(r['reason']=='INSUFFICIENT_HISTORY' for r in blocked)


def test_calibration_each_class_covers_same_sample_and_endpoints():
    cases,_=evaluate(fixture());cells=calibration(cases)
    for method in cases[0]['probabilities']:
        for label in baseline.LABELS:
            assert sum(c['n'] for c in cells if c['method']==method and c['class']==label)==len(cases)
    assert any(c['bin']=='[0.9,1]' and c['mean_predicted']==1 for c in cells)
    assert any(c['bin']=='[0,0.1)' and c['mean_predicted']==0 for c in cells)


def test_real_backtest_training_ids_have_no_historical_leakage():
    rows,_,companies,_=load_observations();lookup={r['id']:r for r in rows}
    saved=json.loads((Path(__file__).resolve().parents[2]/'earnings/reports/backtest_walkforward.json').read_text())
    assert len(companies)==73 and len(rows)==546
    assert saved['summary']['n']==len(saved['evaluated'])
    for p in saved['evaluated']:
        when=baseline.aware(p['simulated_prediction_time'])
        for id_ in p['selection']['historical_ids']:
            prior=lookup[id_]
            assert prior['period_end']<p['period_end']
            assert baseline.aware(prior['public_available_at'])<=when
        assert all(sum(Decimal(v) for v in probs.values())==1 for probs in p['probabilities'].values())


def test_pooled_benchmark_uses_all_prior_public_companies_without_own_switch():
    from earnings.backtest_walkforward import pooled_base_rate, POOLED
    rows=fixture()
    other=row(8,outcome='within',end='2024-07-31');other['company']='Y'
    rows.append(other)
    cases,_=evaluate(rows)
    target=next(r for r in cases if r['id']=='7')
    # Frozen target uses six own earlier quarters; all-public benchmark also
    # uses Y's already-public later-ended quarter, not target X itself.
    assert target['selection']['counts']=={'below':1,'within':2,'above':3}
    pool=target['pooled_baseline_selection']
    assert pool['counts']=={'below':1,'within':3,'above':3}
    assert pool['sample_size']==7 and '8' in pool['historical_ids'] and '7' not in pool['historical_ids']
    assert target['probabilities'][POOLED]==pooled_base_rate(rows,target['simulated_prediction_time'])['probabilities']
    with localcontext() as ctx:
        ctx.prec=80
        assert abs(target['brier'][POOLED]-Decimal(26)/49)<Decimal('1e-23')


def test_pooled_benchmark_strict_timestamp_and_unavailable_or_ineligible_exclusions():
    from earnings.backtest_walkforward import pooled_base_rate
    from earnings.actuals import Blocked
    import pytest
    when='2024-08-01T04:00:00+00:00'
    prior=row(1,public='2024-08-01T03:59:59.999999+00:00')
    at=row(2,public=when);after=row(3,public='2024-08-01T04:00:00.000001+00:00')
    blocked=row(4);blocked['status']='blocked'
    assert pooled_base_rate([prior,at,after,blocked],when)['historical_ids']==['1']
    with pytest.raises(Blocked):pooled_base_rate([at,after,blocked],when)
    with pytest.raises(ValueError,match='one version'):pooled_base_rate([prior,{**prior,'id':'duplicate'}],when)


def test_wilson_interval_hand_reference_and_zero_or_all_successes():
    from earnings.backtest_walkforward import wilson_interval
    import pytest
    ci=wilson_interval(4,532)
    assert abs(ci['low']-Decimal('0.002927685648253535'))<Decimal('1e-18')
    assert abs(ci['high']-Decimal('0.019171124784883501'))<Decimal('1e-18')
    assert wilson_interval(0,28)['low']==0
    assert wilson_interval(28,28)['high']==1
    with pytest.raises(ValueError):wilson_interval(1,0)


def test_saved_pooled_ids_are_strictly_available_and_subgroups_partition_sample():
    from earnings.backtest_walkforward import POOLED
    rows,_,_,_=load_observations();lookup={r['id']:r for r in rows}
    saved=json.loads((Path(__file__).resolve().parents[2]/'earnings/reports/backtest_walkforward.json').read_text())
    for p in saved['evaluated']:
        when=baseline.aware(p['simulated_prediction_time']);pool=p['pooled_baseline_selection']
        assert p['id'] not in pool['historical_ids']
        expected={r['id'] for r in rows if baseline.aware(r['public_available_at'])<when}
        assert set(pool['historical_ids'])==expected
        assert sum(pool['counts'].values())==pool['sample_size']==len(expected)
        assert Decimal(p['brier'][POOLED])==baseline.brier(p['probabilities'][POOLED],p['outcome'])
    assert sum(g['n'] for g in saved['by_history_mode'].values())==saved['summary']['n']==532
    assert sum(g['n'] for g in saved['below_by_sector'].values())==532
    assert sum(g['below'] for g in saved['below_by_sector'].values())==4
    assert sum(g['outcomes'].get('below',0) for g in saved['by_history_mode'].values())==4
