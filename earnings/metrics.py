"""Reported companyfacts metrics. Never derive EPS or mix period/basis inputs."""
from datetime import date
from decimal import Decimal, localcontext
from .actuals import parse_companyfacts, snapshot, Blocked
from .models import plain

DEFINITIONS = {
    'gross_profit': ('GrossProfit',),
    'operating_income': ('OperatingIncomeLoss',),
    'net_income': ('NetIncomeLoss', 'ProfitLoss'),
    'eps_diluted': ('EarningsPerShareDiluted',),
    'operating_cash_flow': ('NetCashProvidedByUsedInOperatingActivities',),
    'capex': ('PaymentsToAcquirePropertyPlantAndEquipment',),
}
LABELS = {'revenue': 'Revenue', 'revenue_growth': 'Revenue growth YoY', 'gross_margin': 'Gross margin',
          'operating_margin': 'Operating margin', 'net_income': 'Net income', 'eps_diluted': 'Diluted EPS',
          'operating_cash_flow': 'Operating cash flow', 'free_cash_flow': 'Free cash flow (CFO − PP&E)'}


def parse_metrics(company, payload):
    result = []
    for key, concepts in {'revenue': (company['concept'],), **DEFINITIONS}.items():
        for concept in concepts:
            for a in parse_companyfacts({**company, 'concept': concept}, payload):
                expected_unit = 'USD/shares' if key == 'eps_diluted' else 'USD'
                if a.unit == expected_unit:
                    result.append((key, a))
    return result


def display(value, unit='USD'):
    if value is None:
        return 'Unavailable'
    if unit == 'ratio':
        return f'{value * Decimal(100):,.2f}%'
    if unit == 'USD/shares':
        return f'{"-" if value < 0 else ""}${abs(value):,.2f}'
    return f'{"-" if value < 0 else ""}${abs(value) / Decimal(1000000):,.3f}M'


def evidence(a):
    return {'id': a.id, **plain(a)}


def financial_overview(company, metric_facts, cutoff):
    available = {}
    conflicts = set()
    for key in ('revenue', *DEFINITIONS):
        try:
            available[key] = snapshot([a for k, a in metric_facts if k == key], cutoff)
        except Blocked:
            available[key] = []
            conflicts.add(key)
    revenues = available['revenue']
    quarters = [a for a in revenues if 75 <= (a.end-a.start).days+1 <= 105]
    annuals = [a for a in revenues if 350 <= (a.end-a.start).days+1 <= 375]
    year_start = date.fromisoformat(company['period_start'])
    ytds = [a for a in revenues if a.start == year_start and a.end < date.fromisoformat(company['period_end'])]
    anchors = {'quarter': max(quarters, key=lambda a: a.end, default=None),
               'ytd': max(ytds, key=lambda a: a.end, default=None),
               'annual': max(annuals, key=lambda a: a.end, default=None)}
    panels = []
    for period_type, anchor in anchors.items():
        def pick(key):
            if anchor is None:
                return None
            candidates = [a for a in available[key] if a.start == anchor.start and a.end == anchor.end]
            concepts = (company['concept'],) if key == 'revenue' else DEFINITIONS.get(key, ())
            for concept in concepts:
                compatible = [a for a in candidates if a.concept == concept and a.accession == anchor.accession]
                if len(compatible) == 1:
                    return compatible[0]
            return None
        cells = []
        with localcontext() as ctx:
            ctx.prec = 50
            for key, label in LABELS.items():
                value = None; parents = []; formula = None; reason = 'No matching reported fact in the revenue filing and exact fiscal period.'
                unit = 'ratio' if key.endswith('margin') or key == 'revenue_growth' else 'USD/shares' if key == 'eps_diluted' else 'USD'
                direct = pick(key) if key in available else None
                if direct:
                    value = direct.value; parents = [direct]
                elif key in ('gross_margin', 'operating_margin') and anchor and anchor.value > 0:
                    numerator = pick('gross_profit' if key == 'gross_margin' else 'operating_income')
                    if numerator:
                        value = numerator.value / anchor.value; parents = [numerator, anchor]
                        formula = 'Reported income / reported revenue; exact period, accession, USD, US GAAP.'
                elif key == 'free_cash_flow':
                    cfo, capex = pick('operating_cash_flow'), pick('capex')
                    if cfo and capex and capex.value >= 0:
                        value = cfo.value - capex.value; parents = [cfo, capex]
                        formula = 'Operating cash flow minus PP&E purchases. Excludes additional company-specific FCF adjustments.'
                elif key == 'revenue_growth' and anchor:
                    previous_end = company['comparison_ends'].get(str(anchor.end))
                    if period_type == 'annual':
                        previous = [a for a in annuals if a.end < anchor.start and a.end.month == anchor.end.month and abs((anchor.end-a.end).days-365) <= 7]
                    else:
                        duration = (anchor.end-anchor.start).days
                        previous = [a for a in revenues if previous_end and str(a.end) == previous_end and abs((a.end-a.start).days-duration) <= (0 if company['calendar']=='weeks' else 1)]
                    if company.get('comparability', {}).get('blocked'):
                        reason = 'Comparison scope unresolved; reported revenue remains available.'
                    elif len(previous) == 1 and previous[0].value > 0:
                        p = previous[0]
                        if company['calendar'] != 'weeks' or (p.end-p.start).days == (anchor.end-anchor.start).days:
                            value = anchor.value / p.value - Decimal(1); parents = [anchor, p]
                            formula = 'Reported revenue / corresponding prior-year revenue − 1; no scope normalization.'
                if key in conflicts:
                    value = None; parents = []; reason = 'Conflicting source versions require review.'
                cells.append({'key': key, 'label': label, 'value': str(value) if value is not None else None,
                              'display': display(value, unit), 'unit': unit, 'basis': ('Reported US GAAP · parent-attributable' if key == 'net_income' and direct and direct.concept == 'NetIncomeLoss' else 'Reported US GAAP · includes noncontrolling interests' if key == 'net_income' and direct and direct.concept == 'ProfitLoss' else 'Reported US GAAP') if not formula else 'Calculated from reported US GAAP',
                              'state': 'available' if value is not None else 'missing', 'reason': None if value is not None else reason,
                              'formula': formula, 'sources': [evidence(a) for a in parents]})
        panels.append({'type': period_type, 'start': str(anchor.start) if anchor else None, 'end': str(anchor.end) if anchor else None,
                       'filed': str(anchor.filed) if anchor else None,
                       'age_days': (cutoff-anchor.end).days if anchor else None,
                       'stale': (cutoff-anchor.end).days > 135 if anchor and period_type != 'annual' else False,
                       'metrics': cells})
    return panels
