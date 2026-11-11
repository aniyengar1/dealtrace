"""Companyfacts ingestion and conservative fiscal-period derivations."""
from datetime import date, timedelta
from .models import Actual, money


class Blocked(ValueError):
    def __init__(self, code, detail):
        self.code, self.detail = code, detail
        super().__init__(f'{code}: {detail}')


def parse_companyfacts(company, payload):
    if str(payload['cik']).zfill(10) != company['cik']:
        raise ValueError('Companyfacts entity mismatch')
    concept = company['concept']
    rows = payload.get('facts', {}).get('us-gaap', {}).get(concept, {}).get('units', {})
    unique = {}
    for unit, facts in rows.items():
        for row in facts:
            if 'start' not in row or row.get('form') not in ('10-K', '10-Q', '10-K/A', '10-Q/A'):
                continue
            if row.get('val') is None:
                continue  # A missing observation remains absent; it never becomes zero.
            a = Actual(company['ticker'], concept, date.fromisoformat(row['start']),
                       date.fromisoformat(row['end']), money(row['val']), unit,
                       company['basis'], row['accn'], date.fromisoformat(row['filed']),
                       row['form'], row.get('fy'), row.get('fp'),
                       f'https://data.sec.gov/api/xbrl/companyfacts/CIK{company["cik"]}.json')
            unique[a.id] = a
    return list(unique.values())


def snapshot(actuals, cutoff):
    """Latest public version per exact period/basis; never pick a conflicting tie."""
    groups = {}
    for a in actuals:
        if a.filed <= cutoff:
            key = (a.company, a.concept, a.start, a.end, a.unit, a.basis)
            groups.setdefault(key, []).append(a)
    result = []
    for group in groups.values():
        latest_day = max(a.filed for a in group)
        latest = [a for a in group if a.filed == latest_day]
        if len({a.value for a in latest}) > 1:
            raise Blocked('INCOMPARABLE_BASIS', 'Conflicting revenue versions filed on the same date')
        result.append(max(latest, key=lambda a: (a.accession, a.id)))
    return result


def exactly(actuals, start, end, company, concept, basis, unit='USD'):
    period = [a for a in actuals if a.company == company and a.start == start and a.end == end]
    compatible = [a for a in period if (a.concept, a.basis, a.unit) == (concept, basis, unit)]
    if len(compatible) != 1:
        raise Blocked('INCOMPARABLE_BASIS' if period else 'MISSING_PERIOD', f'Need one compatible fact for {start} through {end}')
    return compatible[0]


def derive_remaining(annual, ytd):
    if (annual.company, annual.concept, annual.unit, annual.basis) != (ytd.company, ytd.concept, ytd.unit, ytd.basis):
        raise Blocked('INCOMPARABLE_BASIS', 'Annual and YTD entity/concept/unit/basis differ')
    if annual.start != ytd.start or not annual.start <= ytd.end < annual.end:
        raise Blocked('MISSING_PERIOD', 'Annual and YTD boundaries do not nest exactly')
    return Actual(annual.company, annual.concept, ytd.end + timedelta(days=1), annual.end,
                  annual.value - ytd.value, annual.unit, annual.basis,
                  annual.accession, max(annual.filed, ytd.filed), 'DERIVED',
                  annual.fiscal_year, 'REMAINING', annual.source_url,
                  (annual.id, ytd.id), 'annual-minus-ytd-v1')


def derive_q4(annual, nine_month, *, expected_ytd_end, expected_annual_end, calendar):
    """Explicit boundaries required; fiscal labels alone never establish a Q4."""
    if nine_month.end != expected_ytd_end or annual.end != expected_annual_end:
        raise Blocked('MISSING_PERIOD', 'Q4 expected boundaries do not match facts')
    result = derive_remaining(annual, nine_month)
    ytd_days = (nine_month.end - annual.start).days + 1
    q4_days = (annual.end - nine_month.end).days
    if calendar == 'weeks':
        valid = ytd_days == 273 and q4_days in (91, 98) and (annual.end - annual.start).days + 1 in (364, 371)
    elif calendar == 'months':
        valid = (nine_month.end.month - annual.start.month) % 12 == 8 and 89 <= q4_days <= 92 and 365 <= (annual.end - annual.start).days + 1 <= 366
    else:
        valid = False
    if not valid:
        raise Blocked('MISSING_PERIOD', 'Inputs do not describe nine fiscal months plus Q4')
    return result
