from copy import deepcopy
from decimal import Decimal
import pytest
from earnings.pilot_s5.collect import sample,groups
from earnings.pilot_s5.calendar import resolve,adapter

def test_sample_deterministic_and_issuer_stratified():
    gs=[{'id':f'{t}:{q}','company':str(t)} for t in range(20) for q in range(8)]
    result=sample(gs)
    assert result==sample(list(reversed(gs)))
    assert len(result)==30 and len({g['id'] for g in result})==30
    assert {g['company'] for g in result}=={str(t) for t in range(20)}

def test_unknown_weekly_calendar_abstains():
    with pytest.raises(ValueError):resolve({'boundaries':{},'monthly_policy':None},2027,4)

def test_general_monthly_calendar_not_january_default():
    reg={'boundaries':{},'monthly_policy':{'kind':'months','end_year_offset':0,'end_month':4,'start_month':5}}
    assert resolve(reg,2026,2)==('2025-08-01','2025-10-31')
    assert resolve(reg,2026)==('2025-05-01','2026-04-30')

def test_exact_53_week_bounds_preserved():
    r={'boundaries':{'2026:4':{'start':'2026-07-26','end':'2026-10-31'}},'monthly_policy':None}
    assert resolve(r,2026,4)==('2026-07-26','2026-10-31')

def test_adapter_restores_original_issuer_rules_even_on_error():
    from earnings.extraction.v2 import rules
    original=rules.period;calendars=rules.CALENDARS;before={t:original(t,2026,3) for t in calendars['companies']}
    with pytest.raises(RuntimeError):
        with adapter([{'company':'TEST','boundaries':{},'monthly_policy':None}]):
            assert {t:rules.period(t,2026,3) for t in calendars['companies']}==before
            with pytest.raises(ValueError):rules.period('TEST',2026,3)
            raise RuntimeError()
    assert rules.period is original and rules.CALENDARS is calendars

def test_freeze_and_sealed_gold_are_unchanged():
    import hashlib
    from earnings.pilot_s5.evaluate import verify_freeze
    from earnings.pilot_s5.collect import ROOT,read
    verify_freeze()
    assert hashlib.sha256((ROOT/'gold.json').read_bytes()).hexdigest()==read(ROOT/'gold_seal.json')['gold_sha256']
    assert len(read(ROOT/'sample.json')['groups'])==30
    assert len(read(ROOT/'gold.json')['release_reviews'])==30
    assert len(read(ROOT/'gold.json')['records'])==49

def test_uncertainty_zero_denominator_is_missing_not_perfect():
    from earnings.pilot_s5.evaluate import interval
    assert interval(0,0) is None
    zero=interval(0,20);full=interval(20,20)
    assert Decimal(zero['low'])==0 and Decimal(zero['high'])>0
    assert Decimal(full['low'])<1 and Decimal(full['high'])==1

def test_audited_misses_and_empty_quarter_remain_in_sample():
    from earnings.pilot_s5.collect import ROOT,read
    gold=read(ROOT/'gold.json');reviews=gold['release_reviews']
    assert any(r['company']=='COO' for r in reviews)
    assert not any(g['company']=='COO' and g['metric']=='quarterly_consolidated_revenue' for g in gold['records'])
    assert {g['company'] for g in gold['records']}=={r['company'] for r in reviews}
    assert all(r['outputs_hidden_at_label_creation'] for r in reviews)

def test_dollar_tolerance_labels_do_not_claim_verbatim_endpoints():
    from earnings.pilot_s5.collect import ROOT,read
    rows=[g for g in read(ROOT/'gold.json')['records'] if 'normalization' in g]
    assert len(rows)==7
    for g in rows:
        n=g['normalization'];b=Decimal(n['base_millions'])*1000000;d=Decimal(n['tolerance_millions'])*1000000
        assert Decimal(g['low'])==b-d and Decimal(g['high'])==b+d
        assert n['endpoints_verbatim'] is False

def test_actual_selection_preserves_earliest_version_and_raw_scale():
    from datetime import date
    from earnings.models import Actual
    from earnings.pilot_s5.assemble import actual_for
    original=Actual('TEST','Revenues',date(2025,1,1),date(2025,3,31),Decimal('1018308'),'USD','reported','original',date(2025,5,1),'10-Q',2025,'Q1','https://data.sec.gov/example')
    revision=Actual('TEST','Revenues',original.start,original.end,Decimal('1018308000'),'USD','reported','later',date(2025,8,1),'10-Q',2025,'Q1','https://data.sec.gov/example')
    selected,block=actual_for([revision,original],'2025-01-01','2025-03-31')
    assert selected is original and selected.value==Decimal('1018308') and block is None

def test_conflicting_original_actuals_block():
    from dataclasses import replace
    from datetime import date
    from earnings.models import Actual
    from earnings.pilot_s5.assemble import actual_for
    a=Actual('TEST','Revenues',date(2025,1,1),date(2025,3,31),Decimal('10'),'USD','reported','a',date(2025,5,1),'10-Q',2025,'Q1','https://data.sec.gov/example')
    b=replace(a,value=Decimal('11'),accession='b')
    assert actual_for([a,b],'2025-01-01','2025-03-31')==(None,'CONFLICTING_EARLIEST_FACT_VALUES')

def test_sample_scope_blocks_are_not_growth_blocks_or_silent_adjustments():
    from earnings.pilot_s5.collect import ROOT,read
    rs={r['sample_index']:r for r in read(ROOT/'result_reviews.json')['reviews']}
    assert rs[19]['block']=='ACQUISITION_TARGET_SCOPE_MISMATCH' and rs[19]['outcome'] is None
    assert rs[23]['actual']['value']=='1018308' and rs[23]['reported_value']=='1018308000'
    assert rs[23]['block']=='SOURCE_FACT_SCALE_MISMATCH'
    assert rs[27]['block'] is None and rs[27]['outcome']=='within'

def test_period_inventory_has_no_duplicate_or_invented_quarters():
    from datetime import date
    from earnings.pilot_s5.collect import ROOT,read
    rows=read(ROOT/'coverage_reviewed.json')['rows']
    assert len(rows)==160 and all(r['target_period'] for r in rows)
    keys={(r['company'],r['target_period']['start'],r['target_period']['end']) for r in rows}
    assert len(keys)==160
    assert all(80<=(date.fromisoformat(r['target_period']['end'])-date.fromisoformat(r['target_period']['start'])).days+1<=110 for r in rows)
    supplements=read(ROOT/'period_inventory_supplements.json')['evidence']
    for company,days in [('SANM',98),('PLXS',91)]:
        p=next(s['target_period'] for s in supplements if s['company']==company)
        assert (date.fromisoformat(p['end'])-date.fromisoformat(p['start'])).days+1==days
    assert sum(r['target_period'] is None for r in read(ROOT/'coverage.json')['rows'])==8

def test_manual_gold_quotes_reconcile_to_pinned_sources_offline():
    import hashlib
    from earnings.pilot_s5.collect import ROOT,read
    from earnings.pilot_s5.review import raw
    from earnings.extraction.corpus import canonical
    gold=read(ROOT/'gold.json');sources={r['source_url']:canonical(raw(r['source_manifest'])) for r in gold['release_reviews']}
    for g in gold['records']:
        assert sources[g['source_url']][g['quote_start']:g['quote_end']]==g['quote']
        assert Decimal(g['low'])<=Decimal(g['high'])
