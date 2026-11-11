from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal as D
import pytest
from earnings.models import Actual, Guidance, DateInterval, Policy, money
from earnings.actuals import Blocked, derive_q4, derive_remaining, parse_companyfacts, snapshot
from earnings.engine import hurdle, outcomes, attribution

DAY = date.fromisoformat
COMPANY = {'ticker':'TEST','cik':'0000000001','concept':'Revenues','basis':'GAAP','calendar':'months',
           'period_start':'2026-02-01','period_end':'2027-01-31',
           'prior_start':'2025-02-01','prior_end':'2026-01-31',
           'comparison_ends':{'2026-10-31':'2025-10-31'}}


def actual(start, end, value, filed='2026-11-01', **kwargs):
    return Actual('TEST','Revenues',DAY(start),DAY(end),D(value),'USD','GAAP',
                  '0000000001-26-000001',DAY(filed),'10-Q',2027,'Q3','https://data.sec.gov/example',**kwargs)


def guidance(status='initial', low='1000000000', high='1050000000', issued='2026-10-01', **kwargs):
    return Guidance('TEST',DateInterval.read(issued),DAY(issued),DAY('2026-02-01'),DAY('2027-01-31'),
                    None if status=='withdrawn' else D(low),None if status=='withdrawn' else D(high),
                    'USD','GAAP',status,'0000000001-26-000002','99.1',
                    'https://www.sec.gov/Archives/example','Revenue guidance evidence',
                    original_verified=status=='initial',**kwargs)


@pytest.fixture
def facts():
    return [actual('2026-02-01','2026-10-31','700000000'),
            actual('2025-02-01','2026-01-31','900000000','2026-03-01'),
            actual('2025-02-01','2025-10-31','700000000','2025-11-01')]


def calc(facts, history=None, **kwargs):
    return hurdle(COMPANY,facts,history or [guidance()],kwargs.pop('cutoff',DAY('2026-11-11')),**kwargs)


def test_blueprint(facts):
    r=calc(facts)
    assert r.state=='ok'
    assert (r.remaining_low,r.remaining_high)==(D('300000000'),D('350000000'))
    assert (r.growth_low,r.growth_high)==(D('.5'),D('.75'))
    assert len(r.inputs)==5 and r.id==calc(facts).id


def test_zero_and_negative_denominators(facts):
    facts[1]=replace(facts[1],value=D('700000000'))
    assert calc(facts).codes==('ZERO_DENOMINATOR',)
    facts[1]=replace(facts[1],value=D('600000000'))
    assert calc(facts).codes==('INCOMPARABLE_BASIS',)


def test_negative_residual_not_clamped(facts):
    facts[0]=replace(facts[0],value=D('1100000000'))
    r=calc(facts)
    assert r.codes==('NEGATIVE_RESIDUAL',) and r.state=='review'
    assert r.remaining_low==D('-100000000') and r.growth_low==D('-1.5')


def test_missing_withdrawn_and_mismatched_basis(facts):
    assert calc(facts[1:]).codes==('MISSING_PERIOD',)
    assert calc(facts,[guidance('withdrawn')]).codes==('GUIDANCE_WITHDRAWN',)
    assert calc(facts,[replace(guidance(),basis='organic')]).codes==('INCOMPARABLE_BASIS',)


@pytest.mark.parametrize('field,limit', [('actual_days',135),('guidance_days',150)])
def test_staleness_boundaries(facts,field,limit):
    cutoff=DAY('2026-11-11')
    if field=='actual_days':
        # Keep evidenced fiscal boundaries; move the cutoff instead.
        cutoff=facts[0].end+timedelta(days=limit)
        g=guidance(issued=str(cutoff-timedelta(days=10)))
    else:
        g=guidance(issued=str(cutoff-timedelta(days=limit)))
    r=calc(facts,[g],cutoff=cutoff)
    assert 'STALE_INPUT' not in r.codes
    r=calc(facts,[g],cutoff=cutoff+timedelta(days=1))
    assert r.codes==('STALE_INPUT',)
    assert field in r.details[0] and r.inputs['guidance']==g.id


def test_manual_policy_version_and_threshold(facts):
    p=Policy('custom-v2',0,0)
    r=calc(facts,policy=p)
    assert r.codes==('STALE_INPUT',) and len(r.details)==2 and r.policy==p
    assert attribution(calc(facts),r)==['manual_policy_changed','eligibility_or_freshness_changed']


def test_historical_filter_and_restatements(facts):
    future=replace(facts[0],value=D('800000000'),filed=DAY('2026-11-12'),accession='amended')
    assert calc(facts+[future]).growth_low==D('.5')
    assert calc(facts+[future],cutoff=DAY('2026-11-12')).remaining_low==D('200000000')
    assert future.id!=facts[0].id
    assert len(snapshot(facts+[future],DAY('2026-11-11')))==3
    future_guidance=replace(guidance(),filed=DAY('2026-11-12'),low=D('1100000000'),high=D('1200000000'))
    assert calc(facts,[guidance(),future_guidance]).inputs['guidance']==guidance().id


def test_issuance_and_filing_both_required(facts):
    g=replace(guidance(),issued=DateInterval.read('2026-11-12'),filed=DAY('2026-11-01'))
    assert calc(facts,[g]).codes==('MISSING_PERIOD',)
    g=replace(g,issued=DateInterval.read({'start':'2026-11-01','end':'2026-11-30','precision':'month'}))
    assert calc(facts,[g]).codes==('MISSING_PERIOD',)


def test_no_float_or_zero_imputation():
    with pytest.raises(ValueError):money(1.5)
    with pytest.raises(TypeError):money(None)
    with pytest.raises(ValueError):replace(guidance(),low=None)
    with pytest.raises(ValueError):replace(guidance('withdrawn'),low=D(0))


def test_q4_and_incompatible_inputs(facts):
    annual,ytd=facts[1:]
    q4=derive_q4(annual,ytd,expected_ytd_end=DAY('2025-10-31'),expected_annual_end=DAY('2026-01-31'),calendar='months')
    assert q4.value==D('200000000') and q4.start==DAY('2025-11-01')
    assert q4.parents==(annual.id,ytd.id)
    for bad,code in [(replace(ytd,start=DAY('2025-02-02')),'MISSING_PERIOD'),
                     (replace(ytd,basis='organic'),'INCOMPARABLE_BASIS'),
                     (replace(ytd,concept='OtherRevenue'),'INCOMPARABLE_BASIS'),
                     (replace(ytd,unit='EUR'),'INCOMPARABLE_BASIS')]:
        with pytest.raises(Blocked) as e:derive_remaining(annual,bad)
        assert e.value.code==code
    with pytest.raises(Blocked):derive_q4(annual,replace(ytd,end=DAY('2025-07-31')),
        expected_ytd_end=DAY('2025-07-31'),expected_annual_end=annual.end,calendar='months')


@pytest.mark.parametrize('weeks',[52,53])
def test_week_based_q4(weeks):
    start=DAY('2025-02-02');end=start+timedelta(weeks=weeks)-timedelta(days=1)
    annual=actual(str(start),str(end),'900');ytd=actual(str(start),str(start+timedelta(weeks=39)-timedelta(days=1)),'700')
    q4=derive_q4(annual,ytd,expected_ytd_end=ytd.end,expected_annual_end=end,calendar='weeks')
    assert (q4.end-q4.start).days+1==(weeks-39)*7


def test_week_mismatch_blocks(facts):
    c={**COMPANY,'calendar':'weeks','period_end':'2027-02-07'}
    assert hurdle(c,facts,[replace(guidance(),end=DAY('2027-02-07'))],DAY('2026-11-11')).codes==('INCOMPARABLE_BASIS',)


def test_conflicting_revisions_not_arbitrarily_selected(facts):
    with pytest.raises(Blocked):snapshot(facts+[replace(facts[0],value=D(1),accession='other')],DAY('2026-11-11'))
    assert calc(facts,[guidance(),replace(guidance(),low=D('999'))]).codes==('INCOMPARABLE_BASIS',)


def test_reproducible_ingestion():
    c={**COMPANY,'concept':'Revenues'}
    row={'start':'2026-02-01','end':'2026-07-31','val':245403000,'filed':'2026-08-27','accn':'a','form':'10-Q','fy':2027,'fp':'Q2'}
    payload={'cik':1,'facts':{'us-gaap':{'Revenues':{'units':{'USD':[row,row,{**row,'val':245404000,'accn':'b','filed':'2026-09-01','form':'10-Q/A'}]}}}}}
    a=parse_companyfacts(c,payload)
    assert len(a)==2 and a==parse_companyfacts(c,payload)
    assert snapshot(a,DAY('2026-08-31'))[0].value==D('245403000')
    with pytest.raises(ValueError):parse_companyfacts({**c,'cik':'0000000002'},payload)


def test_attribution(facts):
    a=calc(facts);b=calc([replace(facts[0],value=D('710000000'))]+facts[1:],[replace(guidance(),low=D('1010000000'))])
    assert attribution(a,b)==['guidance_changed','actuals_arrived_or_revised']
    b=calc(facts[:1]+[replace(facts[1],value=D('910000000'))]+facts[2:])
    assert attribution(a,b)==['prior_comparison_changed']


def annual_outcome(history, value='1000000000', **kwargs):
    a=actual('2026-02-01','2027-01-31',value,'2027-03-20')
    return outcomes(COMPANY,a,history,cutoff=DAY(kwargs.pop('cutoff','2027-03-20')),
        result_issued=DateInterval.read('2027-03-10'),
        result_source={'accession':'annual-release','url':'https://www.sec.gov/Archives/release'},**kwargs)


@pytest.mark.parametrize('value,expected',[('999999999','below'),('1000000000','within'),('1050000000','within'),('1050000001','above')])
def test_outcome_inclusive_boundaries(value,expected):
    r=annual_outcome([guidance()],value)
    assert r['original']==r['latest']==expected


def test_withdrawal_reinstatement_and_original():
    original=guidance();withdraw=guidance('withdrawn',issued='2026-11-01')
    r=annual_outcome([original,withdraw]);assert r['original']=='within' and r['original_subsequently_withdrawn']
    assert r['latest'] is None and r['codes']['latest']=='GUIDANCE_WITHDRAWN'
    reinstate=guidance('reinstated',low='1100000000',high='1200000000',issued='2026-12-01')
    r=annual_outcome([original,withdraw,reinstate]);assert r['original']=='within' and r['latest']=='below'
    assert r['original_guidance']==original.id


def test_outcome_requires_original_and_annual_availability():
    r=annual_outcome([guidance('raised')]);assert r['codes']['original']=='ORIGINAL_GUIDANCE_UNAVAILABLE'
    assert annual_outcome([guidance()],comparable=False)['original']=='not_comparable'
    assert annual_outcome([guidance()],cutoff='2027-03-19')['codes']['latest']=='MISSING_PERIOD'
    # Guidance issued on the result date is not an eligible pre-result benchmark.
    r=annual_outcome([guidance(),guidance('raised',low='1200000000',high='1300000000',issued='2027-03-10')])
    assert r['latest']=='within'
