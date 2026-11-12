"""Quarter guidance implied growth and selected-version outcomes; never forecasts.

Quarter targets are explicit fiscal boundaries, not companyfacts fiscal labels.
An unreported quarter is compared directly with last year's matching quarter.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, localcontext

from .actuals import Blocked, exactly, snapshot, derive_q4
from .engine import available_guidance, latest_guidance, classify
from .models import Policy, DateInterval, record_id

METRIC = 'quarterly_consolidated_revenue'


@dataclass(frozen=True)
class QuarterCalculation:
    company: str
    as_of: date
    target: dict
    policy: Policy
    inputs: dict = field(default_factory=dict)
    codes: tuple[str, ...] = ()
    details: tuple[str, ...] = ()
    guidance_low: Decimal | None = None
    guidance_high: Decimal | None = None
    growth_low: Decimal | None = None
    growth_high: Decimal | None = None
    formula_version: str = 'quarter-guidance-implied-growth-v1-decimal50'

    @property
    def id(self):
        return record_id('quarter-calculation-v1', self)

    @property
    def state(self):
        return 'blocked' if self.codes else 'ok'


def review_block(review, cutoff):
    """Unknown/future decisions block; a passed review requires dated evidence."""
    if not review or date.fromisoformat(review['available_on']) > cutoff:
        return 'Comparability review unavailable by cutoff'
    if review.get('blocked', True):
        return review.get('reason', 'Comparability review unresolved')
    sources=review.get('sources')
    if not isinstance(sources,list) or not sources:
        return 'Passing comparability review requires source evidence'
    from urllib.parse import urlparse
    for source in sources:
        url=source.get('url','') if isinstance(source,dict) else source
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.hostname not in ('www.sec.gov','data.sec.gov','sec.gov') or parsed.username or parsed.password or parsed.port:
            return 'Financial comparability review requires SEC source evidence'
        if isinstance(source,dict) and source.get('filed_date') and date.fromisoformat(source['filed_date']) > cutoff:
            return 'Comparability source unavailable by cutoff'
    return None


def prior_quarter(company, target, actuals, cutoff):
    facts = snapshot([a for a in actuals if a.company == company['ticker']], cutoff)
    start, end = map(date.fromisoformat, (target['prior_start'], target['prior_end']))
    args = (company['ticker'], company['concept'], company['basis'])
    direct = [a for a in facts if a.start == start and a.end == end]
    if direct:
        return exactly(facts, start, end, *args)
    if target.get('prior_q4'):
        q4 = target['prior_q4']
        annual = exactly(facts, date.fromisoformat(q4['annual_start']), end, *args)
        ytd_end = date.fromisoformat(q4['nine_month_end'])
        ytd = exactly(facts, annual.start, ytd_end, *args)
        result = derive_q4(annual, ytd, expected_ytd_end=ytd_end,
                           expected_annual_end=end, calendar=company['calendar'])
        if result.start != start:
            raise Blocked('MISSING_PERIOD', 'Derived Q4 does not match target comparison boundaries')
        return result
    raise Blocked('MISSING_PERIOD', f'No compatible prior quarter {start} through {end}')


def implied_growth(company, target, actuals, history, cutoff, policy=Policy()):
    inputs = {}
    def result(code=None, detail=None, **values):
        from copy import deepcopy
        config=deepcopy({k:v for k,v in target.items() if k!='outcome_comparability'})
        review=config.get('growth_comparability')
        if review and date.fromisoformat(review['available_on']) > cutoff:
            config['growth_comparability']={'available_on':review['available_on'],'review_status':'not_available_by_cutoff'}
        return QuarterCalculation(company['ticker'], cutoff, config, policy, inputs.copy(),
            (code,) if code else (), (detail,) if detail else (), **values)
    try:
        if date.fromisoformat(target['available_on']) > cutoff:
            return result('MISSING_PERIOD', 'Target fiscal boundaries unavailable by cutoff')
        start, end = map(date.fromisoformat, (target['start'], target['end']))
        g = latest_guidance(available_guidance(history, cutoff, start, end, company['ticker'], metric=METRIC))
        inputs['guidance'] = g.id
        if g.status == 'withdrawn':
            return result('GUIDANCE_WITHDRAWN', 'Latest quarterly guidance is withdrawn')
        if (g.basis, g.unit) != (company['basis'], 'USD'):
            return result('INCOMPARABLE_BASIS', 'Quarter guidance basis or currency differs')
        facts = snapshot([a for a in actuals if a.company == company['ticker']], cutoff)
        if any(start <= a.start <= a.end <= end for a in facts):
            return result('MISSING_PERIOD', 'Target quarter has reported actuals; use outcome classification, not unreported-quarter implied growth')
        block = review_block(target.get('growth_comparability'), cutoff)
        if block:
            return result('INCOMPARABLE_BASIS', block)
        prior = prior_quarter(company, target, actuals, cutoff)
        inputs['prior_quarter'] = prior.id
        ps, pe = prior.start, prior.end
        if company['calendar'] == 'weeks':
            compatible = (end-start).days == (pe-ps).days and ((end-start).days+1) in (91, 98)
        else:
            compatible = (start.month,start.day,end.month,end.day) == (ps.month,ps.day,pe.month,pe.day)
        if not compatible:
            return result('INCOMPARABLE_BASIS', 'Quarter boundaries or fiscal-week counts differ; no normalization')
        # Prior-year seasonal data is necessarily old; the 135-day CURRENT actual
        # policy is not applied to a historical denominator. Its filed cutoff is.
        age = (cutoff-g.issued.start).days
        if age > policy.guidance_days:
            return result('STALE_INPUT', f'guidance_issue_age_days={age} exceeds guidance_days={policy.guidance_days}')
        if prior.value == 0:
            return result('ZERO_DENOMINATOR', 'Prior-year quarter revenue equals zero')
        if prior.value < 0:
            return result('INCOMPARABLE_BASIS', 'Prior-year quarter revenue is negative')
        with localcontext() as ctx:
            ctx.prec = 50
            return result(guidance_low=g.low, guidance_high=g.high,
                growth_low=g.low/prior.value-Decimal(1), growth_high=g.high/prior.value-Decimal(1))
    except Blocked as exc:
        return result(exc.code, exc.detail)


def selected_outcome(company, target, actual, guidance, *, cutoff, result_issued,
                     result_source, comparability=None, history=None):
    """Score one explicit version, independently of prior-year growth comparability.

    Day-only same-release guidance is excluded; no intraday ordering is invented.
    A result-scoped evidence review is required and retained in the outcome.
    """
    if not isinstance(result_issued, DateInterval):
        raise ValueError('Result issuance requires a date interval')
    if not result_source.get('accession') or not result_source.get('url','').startswith('https://www.sec.gov/Archives/') or not result_source.get('filed_date'):
        raise ValueError('Quarter outcome requires dated SEC result evidence')
    review = comparability if comparability is not None else target.get('outcome_comparability')
    r = {'company': company['ticker'], 'as_of': cutoff, 'metric': METRIC,
         'period_start': target['start'], 'period_end': target['end'],
         'actual': actual.id, 'guidance': guidance.id, 'classification': None,
         'codes': [], 'details': [], 'result_issued': result_issued,
         'result_source': result_source, 'outcome_comparability': review,
         'formula_version': 'selected-quarter-outcome-v1'}
    def blocked(code, detail, not_comparable=False):
        r['codes'] = [code]; r['details'] = [detail]
        if not_comparable: r['classification'] = 'not_comparable'
        r['id'] = record_id('quarter-outcome-v1', r)
        return r
    start, end = map(date.fromisoformat, (target['start'],target['end']))
    if guidance.company != company['ticker'] or guidance.metric != METRIC or (guidance.start,guidance.end) != (start,end):
        return blocked('MISSING_PERIOD', 'Selected guidance is not for this company and quarter')
    benchmark = min(result_issued.start,actual.filed)-timedelta(days=1)
    r['benchmark_cutoff'] = benchmark
    r['history_reviewed'] = history is not None
    if history is not None:
        eligible=available_guidance(history,benchmark,start,end,company['ticker'],metric=METRIC)
        original=eligible[0] if eligible and eligible[0].original_verified else None
        latest=latest_guidance(eligible) if eligible else None
        r['selected_is_original']=original is not None and original.id==guidance.id
        r['selected_is_latest_pre_result']=latest is not None and latest.id==guidance.id
        r['latest_pre_result_status']=latest.status if latest else None
        r['original_subsequently_withdrawn']=bool(original and any(g.status=='withdrawn' for g in eligible))
    if guidance.available_on > benchmark:
        return blocked('MISSING_PERIOD', 'Selected guidance was not public before result announcement')
    if guidance.status == 'withdrawn':
        return blocked('GUIDANCE_WITHDRAWN', 'Selected guidance is withdrawn')
    if (actual.company,actual.start,actual.end) != (company['ticker'],start,end):
        return blocked('MISSING_PERIOD', 'Actual does not cover exactly the target quarter')
    if actual.filed > cutoff or not result_issued.available(cutoff) or date.fromisoformat(str(result_source['filed_date'])) > cutoff or result_issued.start <= end or date.fromisoformat(target['available_on']) > cutoff:
        return blocked('MISSING_PERIOD', 'Quarter result or boundary evidence unavailable by cutoff')
    if (actual.concept,actual.basis,actual.unit) != (company['concept'],guidance.basis,guidance.unit):
        return blocked('INCOMPARABLE_BASIS', 'Guidance and reported quarter actual differ in concept/basis/unit', True)
    block = review_block(review, cutoff)
    if block:
        return blocked('INCOMPARABLE_BASIS', block, True)
    # Reviews are specific to these records: an old/recast decision cannot pass.
    if review.get('actual_id') != actual.id or review.get('guidance_id') != guidance.id:
        return blocked('INCOMPARABLE_BASIS', 'Outcome review does not identify the selected actual and guidance versions', True)
    r['classification'] = classify(actual.value, guidance.low, guidance.high)
    r['id'] = record_id('quarter-outcome-v1', r)
    return r


def attribution(before, after):
    if before.company != after.company or (before.target['start'],before.target['end']) != (after.target['start'],after.target['end']):
        raise ValueError('Cannot attribute changes across companies or target quarters')
    causes=[]
    if before.inputs.get('guidance') != after.inputs.get('guidance'):
        causes.append('guidance_changed')
    if before.inputs.get('prior_quarter') != after.inputs.get('prior_quarter'):
        causes.append('prior_comparison_changed')
    if before.target.get('growth_comparability') != after.target.get('growth_comparability'):
        causes.append('growth_comparability_review_changed')
    if before.policy != after.policy:
        causes.append('manual_policy_changed')
    if before.codes != after.codes:
        causes.append('eligibility_or_freshness_changed')
    return causes or ['unchanged_inputs']
