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
