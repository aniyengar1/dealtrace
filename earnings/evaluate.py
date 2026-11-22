"""Small, explicitly reviewed historical cohort. No random splits or future revisions."""
from datetime import date
from decimal import Decimal, localcontext
import json
from .actuals import snapshot, exactly, Blocked
from .forecast import extrapolate, verdict, METHOD
from .models import plain, record_id
from .registry import ROOT


def evaluate_case(case, company, actuals, as_of):
    cutoff = date.fromisoformat(case['forecast_date'])
    result = {'company': company['ticker'], 'forecast_date': str(cutoff), 'case': case,
              'status': 'blocked', 'reason': None, 'inputs': {}}
    if cutoff > as_of:
        return {'company': company['ticker'], 'forecast_date': str(cutoff), 'status': 'blocked', 'reason': 'FORECAST_DATE_AFTER_EVALUATION', 'inputs': {}}
    if case['scope_status'] != 'reviewed':
        result['reason'] = 'HISTORICAL_SCOPE_REVIEW_REQUIRED'
        return result
    if cutoff >= date.fromisoformat(case['period_end']):
        result['reason'] = 'INVALID_FORECAST_DATE'
        return result
    if any(date.fromisoformat(s['filed_date']) > cutoff for s in case['scope_sources']):
        result['reason'] = 'SCOPE_EVIDENCE_NOT_PUBLIC'
        return result
    try:
        facts = snapshot(actuals, cutoff)
        def fact(start, end):
            return exactly(facts, date.fromisoformat(start), date.fromisoformat(end), company['ticker'], company['concept'], company['basis'])
        a = fact(case['period_start'], case['ytd_end'])
        p = fact(case['prior_start'], case['prior_ytd_end'])
        annual = fact(case['prior_start'], case['prior_end'])
        start, end = date.fromisoformat(case['period_start']), date.fromisoformat(case['period_end'])
        if company['calendar'] == 'weeks':
            if (end-start).days != (annual.end-annual.start).days or (a.end-a.start).days != (p.end-p.start).days:
                raise Blocked('INCOMPARABLE_BASIS', 'Historical fiscal-week counts differ; no normalization')
        elif (start.month,start.day,end.month,end.day,a.end.month,a.end.day) != (annual.start.month,annual.start.day,annual.end.month,annual.end.day,p.end.month,p.end.day):
            raise Blocked('INCOMPARABLE_BASIS', 'Historical month-based fiscal periods differ')
        if (cutoff-a.end).days > 135:
            raise Blocked('STALE_INPUT', 'Historical actuals stale at forecast date')
        result['inputs'] = {role: {'id': f.id, **plain(f)} for role, f in [('current_ytd',a), ('prior_ytd',p), ('prior_annual',annual)]}
        # Earliest reported outcome, not today's restated annual figure.
        candidates = [v for v in actuals if str(v.start) == case['period_start'] and str(v.end) == case['period_end'] and cutoff < v.filed <= as_of and v.unit == 'USD' and v.concept == company['concept']]
        if not candidates:
            raise Blocked('MISSING_OUTCOME', 'No public annual outcome by evaluation cutoff')
        first_day = min(v.filed for v in candidates)
        first = [v for v in candidates if v.filed == first_day]
        if len({v.value for v in first}) != 1:
            raise Blocked('INCOMPARABLE_BASIS', 'Conflicting first reported annual values')
        outcome = min(first, key=lambda v: v.id)
        with localcontext() as ctx:
            ctx.prec = 50
            values = extrapolate(a.value, p.value, annual.value)
            if outcome.value <= 0:
                raise Blocked('ZERO_DENOMINATOR', 'Cannot calculate percentage error')
            result.update(status='evaluated', outcome={'id':outcome.id, **plain(outcome)}, **values,
                          absolute_error=abs(values['estimate']-outcome.value),
                          absolute_percentage_error=abs(values['estimate']/outcome.value-1),
                          benchmark_absolute_error=abs(values['benchmark']-outcome.value),
                          benchmark_absolute_percentage_error=abs(values['benchmark']/outcome.value-1))
            g = case.get('guidance')
            if g and max(date.fromisoformat(g['issued_date']),date.fromisoformat(g['filed_date'])) <= cutoff:
                low, high = Decimal(g['low']), Decimal(g['high'])
                result.update(forecast_verdict=verdict(values['estimate'],low,high), actual_verdict=verdict(outcome.value,low,high))
            else:
                result['classification_gap'] = 'No verified guidance available at forecast date'
    except (Blocked, ValueError) as exc:
        result['reason'] = str(exc)
    return plain(result)


def evaluate(registry, actuals_by_company, as_of, cases=None):
    cases = cases if cases is not None else json.loads((ROOT/'evaluation_cases.json').read_text())
    results = [evaluate_case(c, registry[c['company']], actuals_by_company[c['company']], as_of) for c in cases if c['company'] in actuals_by_company and date.fromisoformat(c['forecast_date']) <= as_of]
    accepted = [r for r in results if r['status'] == 'evaluated']
    count = len(accepted)
    with localcontext() as ctx:
        ctx.prec = 50
        def average(key):
            return sum((Decimal(r[key]) for r in accepted), Decimal(0))/Decimal(count) if count else None
        classifications = [r for r in accepted if 'actual_verdict' in r]
        result = {'as_of': str(as_of), 'method': METHOD, 'status': 'insufficient_validation', 'sample_size': count,
                  'coverage_denominator': len(registry), 'covered_companies': len({r['company'] for r in accepted}),
                  'coverage_definition': 'Supported-company coverage of reviewed historical fiscal-year cases with public forecast inputs and initial annual outcomes. One date per reviewed fiscal year; fiscal labels and horizons differ between companies.',
                  'mae_usd': average('absolute_error'), 'mape': average('absolute_percentage_error'),
                  'benchmark_mae_usd': average('benchmark_absolute_error'), 'benchmark_mape': average('benchmark_absolute_percentage_error'),
                  'classification_samples': len(classifications),
                  'classification_correct': sum(r['actual_verdict'] == r['forecast_verdict'] for r in classifications),
                  'interval_coverage': None, 'cases': results,
                  'missing_companies': [t for t in registry if t not in {r['company'] for r in accepted}],
                  'limitations': ['Too few reviewed cases to validate general forecast skill or calibrate probabilities/intervals.',
                                 'Manually selected supported-company cohort; selection and survivorship bias remain.',
                                 'Historical guidance and acquisition/calendar scope reviews are incomplete outside these cases.',
                                 'Outcomes use the earliest public annual filing; later restatements are not forecast inputs or target replacements.']}
    return plain(result)
