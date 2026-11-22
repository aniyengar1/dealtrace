"""Experimental annual revenue forecast. No fitted parameters or probabilities."""
from decimal import Decimal, localcontext
from datetime import timedelta
from .models import plain, record_id

METHOD = 'seasonal-ytd-growth-v1-decimal50'


def extrapolate(current_ytd, prior_ytd, prior_annual):
    if prior_ytd <= 0 or prior_annual < prior_ytd:
        raise ValueError('Prior YTD must be positive and nest within annual revenue')
    with localcontext() as ctx:
        ctx.prec = 50
        growth = current_ytd / prior_ytd - Decimal(1)
        remainder = prior_annual - prior_ytd
        return {'estimate': current_ytd + remainder * (Decimal(1) + growth),
                'benchmark': current_ytd + remainder, 'observed_growth': growth,
                'prior_remaining': remainder, 'prior_remaining_share': remainder / prior_annual}


def verdict(estimate, low, high):
    # Point guidance is the degenerate inclusive range: only equality is meet.
    return 'miss' if estimate < low else 'beat' if estimate > high else 'meet'


def forecast(calculation, actuals, guidance):
    result = {'method': METHOD, 'status': 'experimental', 'as_of': calculation.as_of,
              'estimate': None, 'benchmark': None, 'verdict': None,
              'interval': None, 'interval_reason': 'No calibrated prediction interval; insufficient reviewed historical cases.',
              'probabilities': None, 'inputs': calculation.inputs.copy(),
              'codes': list(calculation.codes), 'details': list(calculation.details),
              'assumptions': ['Prior-year seasonality persists.', 'Observed YTD revenue growth persists through the remaining fiscal period.',
                              'No automatic acquisition, currency, or fiscal-week normalization.',
                              'Does not model future inflections or quarterly outlooks; annual guidance is comparison only.'],
              'hurdle_id': calculation.id, 'policy': plain(calculation.policy)}
    if calculation.state != 'ok':
        result['status'] = 'blocked'
    else:
        facts = {a.id: a for a in actuals}
        guides = {g.id: g for g in guidance}
        try:
            a, p, annual = [facts[calculation.inputs[k]] for k in ('actual_ytd', 'prior_ytd', 'prior_annual')]
            g = guides[calculation.inputs['guidance']]
            if p.value <= 0:
                raise ValueError('Prior-year YTD revenue must be positive')
            values = extrapolate(a.value, p.value, annual.value)
            result.update(values)
            result['verdict'] = verdict(values['estimate'], g.low, g.high)
            result['drivers'] = {'actual_ytd': a.value, 'prior_ytd': p.value, 'prior_annual': annual.value,
                                 'remaining_start': str(a.end + timedelta(days=1)), 'period_end': str(g.end)}
        except (KeyError, ValueError) as exc:
            result.update(status='blocked', codes=['INSUFFICIENT_HISTORY'], details=[str(exc)])
    result['id'] = record_id('forecast-v1', result)
    return result
