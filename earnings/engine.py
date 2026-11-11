"""As-of hurdle, change attribution, and annual outcomes. No forecasting."""
from datetime import date, timedelta
from decimal import Decimal, localcontext
from .actuals import Blocked, snapshot, exactly, derive_remaining
from .models import Calculation, Policy, plain, record_id


def available_guidance(history, cutoff, start, end, company):
    return sorted((g for g in history if g.company == company and g.start == start and g.end == end
                   and g.available_on <= cutoff), key=lambda g: (g.available_on, g.issued.end, g.accession, g.id))


def latest_guidance(history):
    if not history:
        raise Blocked('MISSING_PERIOD', 'No guidance available by cutoff')
    last = history[-1]
    ties = [g for g in history if (g.available_on, g.issued.end) == (last.available_on, last.issued.end)]
    if len({(g.low, g.high, g.status == 'withdrawn', g.basis, g.unit) for g in ties}) > 1:
        raise Blocked('INCOMPARABLE_BASIS', 'Conflicting same-day guidance; ordering needs evidence')
    return last


def _hurdle(company, actuals, guidance, cutoff, policy=Policy()):
    inputs = {}
    def blocked(code, detail):
        return Calculation(company['ticker'], cutoff, policy, inputs.copy(), (code,), (detail,))
    try:
        start, end = map(date.fromisoformat, (company['period_start'], company['period_end']))
        g = latest_guidance(available_guidance(guidance, cutoff, start, end, company['ticker']))
        inputs['guidance'] = g.id
        if g.status == 'withdrawn':
            return blocked('GUIDANCE_WITHDRAWN', 'Latest public guidance is withdrawn')
        review = company.get('comparability', {})
        if review.get('blocked') and date.fromisoformat(review['available_on']) <= cutoff:
            return blocked('INCOMPARABLE_BASIS', review['reason'])
        facts = snapshot(actuals, cutoff)
        if any(a.company == company['ticker'] and a.start == start and a.end == end for a in facts):
            return blocked('MISSING_PERIOD', 'Annual result is available; use annual outcome classification instead of an active hurdle')
        current = [a for a in facts if a.company == company['ticker'] and a.start == start and a.end < end
                   and a.unit == 'USD' and a.basis == company['basis'] and a.concept == company['concept']]
        if not current:
            return blocked('MISSING_PERIOD', 'No compatible current-year YTD revenue')
        ytd = max(current, key=lambda a: a.end)
        inputs['actual_ytd'] = ytd.id
        if (g.basis, g.unit, g.metric) != (ytd.basis, ytd.unit, 'consolidated_revenue'):
            return blocked('INCOMPARABLE_BASIS', 'Guidance and YTD basis/unit/metric differ')
        mapping = company['comparison_ends'].get(str(ytd.end))
        if not mapping:
            return blocked('MISSING_PERIOD', 'No evidenced corresponding prior-year fiscal boundary')
        prior_start = date.fromisoformat(company['prior_start'])
        prior_end = date.fromisoformat(company['prior_end'])
        prior_ytd_end = date.fromisoformat(mapping)
        annual = exactly(facts, prior_start, prior_end, company['ticker'], ytd.concept, ytd.basis, ytd.unit)
        inputs['prior_annual'] = annual.id
        pytd = exactly(facts, prior_start, prior_ytd_end, company['ticker'], ytd.concept, ytd.basis, ytd.unit)
        inputs['prior_ytd'] = pytd.id
        remaining = derive_remaining(annual, pytd)
        inputs['prior_remaining'] = remaining.id
        if company['calendar'] == 'weeks':
            if (end - ytd.end).days != (prior_end - pytd.end).days or (ytd.end - start).days != (pytd.end - prior_start).days:
                return blocked('INCOMPARABLE_BASIS', 'Different fiscal-week counts; no automatic normalization')
        elif (start.month, start.day, end.month, end.day, ytd.end.month, ytd.end.day) != (
                prior_start.month, prior_start.day, prior_end.month, prior_end.day, pytd.end.month, pytd.end.day):
            return blocked('INCOMPARABLE_BASIS', 'Different month-based fiscal boundaries')
        stale = []
        if (cutoff - ytd.end).days > policy.actual_days:
            stale.append(f'actuals_period_age_days={(cutoff-ytd.end).days} exceeds actual_days={policy.actual_days}')
        # Use the earliest possible issue date so an imprecise interval cannot hide staleness.
        if (cutoff - g.issued.start).days > policy.guidance_days:
            stale.append(f'guidance_issue_age_days={(cutoff-g.issued.start).days} exceeds guidance_days={policy.guidance_days}')
        if stale:
            return Calculation(company['ticker'], cutoff, policy, inputs, ('STALE_INPUT',), tuple(stale))
        if remaining.value == 0:
            return blocked('ZERO_DENOMINATOR', 'Prior-year remaining revenue equals zero')
        if remaining.value < 0:
            return blocked('INCOMPARABLE_BASIS', 'Prior-year derived remaining revenue is negative')
        with localcontext() as ctx:
            ctx.prec = 50
            low, high = g.low - ytd.value, g.high - ytd.value
            codes = ('NEGATIVE_RESIDUAL',) if low < 0 or high < 0 else ()
            details = ('Negative residual requires review; values are not clamped',) if codes else ()
            return Calculation(company['ticker'], cutoff, policy, inputs, codes, details,
                               low, high, low / remaining.value - Decimal(1), high / remaining.value - Decimal(1))
    except Blocked as exc:
        return blocked(exc.code, exc.detail)


def attribution(before, after):
    moved = []
    if before.inputs.get('guidance') != after.inputs.get('guidance'):
        moved.append('guidance_changed')
    if before.inputs.get('actual_ytd') != after.inputs.get('actual_ytd'):
        moved.append('actuals_arrived_or_revised')
    if any(before.inputs.get(k) != after.inputs.get(k) for k in ('prior_annual', 'prior_ytd', 'prior_remaining')):
        moved.append('prior_comparison_changed')
    if before.company_config.get('comparability') != after.company_config.get('comparability'):
        moved.append('comparability_review_changed')
    if before.policy != after.policy:
        moved.append('manual_policy_changed')
    if before.codes != after.codes:
        moved.append('eligibility_or_freshness_changed')
    return moved or ['unchanged_inputs']


def classify(value, low, high):
    return 'below' if value < low else 'above' if value > high else 'within'


def outcomes(company, annual, history, *, cutoff, result_issued, result_source, comparable=True):
    """Annual result only. Benchmark cutoff precedes the earnings release, not its later 10-K.

    Day-granularity guidance on the release date is excluded conservatively; intraday
    precedence cannot be established. result_source must identify the dated SEC release.
    """
    if not result_source.get('accession') or not result_source.get('url', '').startswith('https://www.sec.gov/Archives/'):
        raise ValueError('Annual outcome requires an evidenced SEC result announcement')
    start, end = map(date.fromisoformat, (company['period_start'], company['period_end']))
    benchmark_cutoff = result_issued.start - timedelta(days=1)
    eligible = available_guidance(history, benchmark_cutoff, start, end, company['ticker'])
    # The initial range must actually be the first observed version and be verified.
    original = eligible[0] if eligible and eligible[0].original_verified else None
    latest = latest_guidance(eligible) if eligible else None
    withdrawn = any(g.status == 'withdrawn' for g in eligible)
    result = {'company': company['ticker'], 'as_of': cutoff, 'actual': annual.id,
              'result_issued': result_issued, 'result_source': result_source,
              'benchmark_cutoff': benchmark_cutoff, 'original': None, 'latest': None,
              'original_guidance': original.id if original else None,
              'latest_guidance': latest.id if latest else None,
              'original_subsequently_withdrawn': withdrawn, 'codes': {}}
    ready = annual.filed <= cutoff and result_issued.available(cutoff) and result_issued.start > end
    valid_period = (annual.company, annual.start, annual.end) == (company['ticker'], start, end)
    valid_basis = (annual.concept, annual.unit, annual.basis) == (company['concept'], 'USD', company['basis'])
    for label, g in [('original', original), ('latest', latest)]:
        if not ready or not valid_period:
            result['codes'][label] = 'MISSING_PERIOD'
        elif g is None:
            result['codes'][label] = 'ORIGINAL_GUIDANCE_UNAVAILABLE' if label == 'original' else 'MISSING_PERIOD'
        elif g.status == 'withdrawn':
            result['codes'][label] = 'GUIDANCE_WITHDRAWN'
        elif not comparable or not valid_basis or (company.get('comparability', {}).get('blocked') and date.fromisoformat(company['comparability']['available_on']) <= cutoff):
            result[label] = 'not_comparable'
        elif (g.basis, g.unit) != (annual.basis, annual.unit):
            result[label] = 'not_comparable'
        else:
            result[label] = classify(annual.value, g.low, g.high)
    result['id'] = record_id('outcome-v1', result)
    return result


def hurdle(company, actuals, guidance, cutoff, policy=Policy()):
    from dataclasses import replace
    from copy import deepcopy
    config = deepcopy({k: v for k, v in company.items() if k not in ('next_report', 'annual_result')})
    review = config.get('comparability', {})
    if review and date.fromisoformat(review['available_on']) > cutoff:
        config['comparability'] = {'review_status': 'not_available_by_cutoff'}
    return replace(_hurdle(company, actuals, guidance, cutoff, policy), company_config=config)
