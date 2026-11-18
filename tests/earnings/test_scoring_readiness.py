from pathlib import Path
from decimal import Decimal
from copy import deepcopy
import json
import pytest
from earnings import score_live,baseline
from earnings.engine import classify
from earnings.scoring_readiness import review_for,cases
from earnings import history
from earnings.actuals import Blocked


def historical_fixture():
    rows=history.load_all()
    row,b,asof=cases({'historical_observations':[{'payload':r,'recorded_at':r['source_record']['outcome_basis_review']['reviewed_at']} for r in rows]})[1]
    g=next(g for g in row['source_record']['guidance_versions'] if g['id']==row['guidance_id'])
    prediction={'id':'retrospective-fixture-not-live','made_at':asof.isoformat(),'guidance_id':g['id'],'snapshot':{'locked_guidance':g},**{'p_'+k:v for k,v in b['probabilities'].items()}}
    return prediction,review_for(row)

@pytest.mark.parametrize('value,expected',[('99','below'),('100','within'),('150','within'),('200','within'),('201','above')])
def test_exact_inclusive_boundaries(value,expected):
    assert classify(Decimal(value),Decimal(100),Decimal(200))==expected


def test_point_guidance_and_zero_bucket_brier_remain_frozen():
    assert classify(Decimal(100),Decimal(100),Decimal(100))=='within'
    assert baseline.brier({'below':Decimal(0),'within':Decimal(0),'above':Decimal(1)},'below')==2
    assert baseline.brier({'below':Decimal(0),'within':Decimal(0),'above':Decimal(1)},'above')==0
    assert not hasattr(score_live,'log_score') and not hasattr(baseline,'log_score')

@pytest.mark.parametrize('fault,code',[('actual','MISSING_PERIOD'),('basis','INCOMPARABLE_BASIS'),('id','INCOMPARABLE_BASIS'),('publication','NOT_PROSPECTIVE')])
def test_missing_or_incompatible_outcomes_block_without_zero_substitution(fault,code):
    p,r=historical_fixture()
    if fault=='actual':r.pop('actual')
    elif fault=='basis':r['outcome_basis_review']['blocked']=True
    elif fault=='id':r['outcome_basis_review']['guidance_id']='wrong-version'
    elif fault=='publication':r['first_result_publication_lower_bound']=p['made_at']
    with pytest.raises(Blocked) as e:score_live.evaluate(p,r,baseline.aware('2026-11-18T00:00:00Z'))
    assert e.value.code==code


def test_stored_rehearsal_replays_frozen_code_and_never_claims_live():
    evidence=json.loads(Path('earnings/validation/scoring_readiness_2026-11-18.json').read_text())
    assert evidence['live_ledger_mutations']==0 and evidence['prediction_rows_created']==0 and evidence['repeated_run_new_scores']==0 and evidence['incorrect_brier_rejected']
    assert {r['outcome'] for r in evidence['scored_cases']}=={'below','within','above'}
    for r in evidence['scored_cases']:assert Decimal(r['brier'])==baseline.brier(r['probabilities'],r['outcome'])
