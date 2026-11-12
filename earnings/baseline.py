"""Quarterly empirical outcome rates. No model fitting or annual forecast reuse."""
from collections import Counter, defaultdict
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from zoneinfo import ZoneInfo
from .actuals import Blocked
from .models import money

METHOD='quarter-frequency-v1'
LABELS=('below','within','above')
ZONE='America/New_York'


def aware(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
    if not isinstance(result,datetime) or result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('An explicit timezone-aware timestamp is required')
    return result.astimezone(timezone.utc)


def day_available(day):
    """Conservative upper boundary of a day-precision US SEC/issuance interval."""
    d=date.fromisoformat(str(day))
    return datetime.combine(d+timedelta(days=1),time.min,ZoneInfo(ZONE)).astimezone(timezone.utc)


def guidance_cutoff(release_date):
    # Latest fully public guidance at entry to the 14-local-calendar-day window.
    return date.fromisoformat(str(release_date))-timedelta(days=15)


def probabilities(company, rows, prediction_time, *, retrospective=False):
    as_of=aware(prediction_time);versions={}
    for row in rows:
        if (not retrospective and aware(row['recorded_at'])>as_of) or aware(row['public_available_at'])>as_of:
            continue
        key=(row['company'],row['period_start'],row['period_end'])
        if key not in versions or (aware(row['recorded_at']),row['id'])>(aware(versions[key]['recorded_at']),versions[key]['id']):
            versions[key]=row
    groups=defaultdict(list)
    for row in versions.values():groups[row['company']].append(row)
    window={t:sorted(v,key=lambda r:(r['period_end'],r['period_start']),reverse=True)[:8] for t,v in groups.items()}
    eligible={t:[r for r in v if r['status']=='eligible' and r['outcome'] in LABELS] for t,v in window.items()}
    own=eligible.get(company,[])
    if len(own)>=6: selected=own;mode='company'
    else:
        selected=[r for values in eligible.values() for r in values]
        if len(selected)<12 or len({r['company'] for r in selected})<2:
            raise Blocked('INSUFFICIENT_HISTORY','Need six company quarters, or at least twelve pooled eligible quarters from two companies')
        mode='pooled'
    counts=Counter(r['outcome'] for r in selected);n=len(selected)
    with localcontext() as ctx:
        ctx.prec=80
        below=(Decimal(counts['below'])/Decimal(n)).quantize(Decimal('1e-24'),rounding=ROUND_HALF_EVEN)
        within=(Decimal(counts['within'])/Decimal(n)).quantize(Decimal('1e-24'),rounding=ROUND_HALF_EVEN)
        above=Decimal(1)-below-within
    return {'method_version':METHOD,'as_of':as_of.isoformat(),'mode':mode,'sample_size':n,
        'evaluation_kind':'retrospective_reconstruction' if retrospective else 'as_recorded',
        'company_sample_size':len(own),'pool_companies':sorted({r['company'] for r in selected}),
        'counts':{label:counts[label] for label in LABELS},
        'probabilities':dict(zip(LABELS,(below,within,above))),
        'historical_ids':sorted(r['id'] for r in selected),
        'policy':{'quarters_per_company':8,'company_minimum':6,'pool_minimum':12,'pool_company_minimum':2,
                  'smoothing':'none','rounding':'first two rates half-even at 24 places; above receives residual',
                  'guidance_horizon':'entry to 14-day window; day-precision guidance must be public before entry day'},
        'limitations':['Empirical frequencies, not calibrated probabilities or confidence scores.',
                       'Small curated cohort and period-dependent management guidance practices; no predictive-quality claim.']}


def brier(probability, outcome):
    if outcome not in LABELS:raise ValueError('Unknown outcome')
    values={k:money(probability[k]) for k in LABELS}
    with localcontext() as ctx:
        ctx.prec=max(100,2*max(len(v.as_tuple().digits) for v in values.values())+10)
        if any(v<0 or v>1 for v in values.values()) or sum(values.values())!=1:
            raise ValueError('Probabilities must be in [0,1] and sum exactly to one')
        return sum((values[k]-Decimal(k==outcome))*(values[k]-Decimal(k==outcome)) for k in LABELS)
