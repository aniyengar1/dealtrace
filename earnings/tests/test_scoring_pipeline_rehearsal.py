from datetime import datetime,timezone,timedelta
from decimal import Decimal
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from earnings import score_live
from earnings.scoring_pipeline_rehearsal import checked_scratch,synthetic_review,LABEL
from earnings.actuals import Blocked


def prediction(ticker):
    row=next(r for r in json.loads(Path('earnings/publication/predictions.json').read_text())['predictions'] if r['company']==ticker and r['method']=='quarter-frequency-v1')
    return {'id':row['id'],'ticker':ticker,'made_at':row['locked_at'],'guidance_id':row['guidance']['id'],'snapshot':{'locked_guidance':{'company':ticker,'start':row['period_start'],'end':row['period_end'],'low':row['guidance']['low'],'high':row['guidance']['high'],'basis':row['guidance']['basis'],'unit':row['guidance']['unit']}},**{'p_'+k:v for k,v in row['probabilities'].items()}}


def test_every_fabricated_source_is_local_and_all_outcomes_and_endpoints_work():
    clock=datetime(2026,11,22,tzinfo=timezone.utc)
    for ticker,outcome in [('OKTA','below'),('CRM','within'),('IOT','above'),('S','within')]:
        p=prediction(ticker);review,fixtures=synthetic_review(p,clock)
        def fetch(url,**kwargs):
            assert url in fixtures
            return fixtures[url],{'simulation':True}
        with patch('earnings.sec.fetch',fetch):score_live.verify_sources(review)
        evaluated=score_live.evaluate(p,review,clock)
        assert evaluated['outcome']==outcome
        assert LABEL in review['rehearsal_provenance']
        assert 'NOT owner review' in review['outcome_basis_review']['verifier']
        if ticker=='OKTA':assert evaluated['brier']==Decimal(2)
        with pytest.raises(Blocked,match='not publicly available'):
            score_live.evaluate(p,{**review,'evidence_available_at':(clock+timedelta(days=1)).isoformat()},clock)


def test_production_or_ambiguous_dsns_are_rejected_before_connection(monkeypatch):
    def no_connection(*args,**kwargs):raise AssertionError('Must not connect')
    monkeypatch.setattr('earnings.scoring_pipeline_rehearsal.psycopg.connect',no_connection)
    for dsn in ['postgresql://localhost:5432/dealtrace','dbname=dealtrace','host=127.0.0.1 port=65439 dbname=postgres','host=example.com port=65439 dbname=crosscheck_scoring_rehearsal_test']:
        with pytest.raises(ValueError,match='private'):checked_scratch(dsn)


def test_source_availability_cannot_be_forced_by_backdating_a_test_clock():
    with pytest.raises(ValueError,match='No room'):
        synthetic_review(prediction('OKTA'),datetime(2026,11,17,tzinfo=timezone.utc))
