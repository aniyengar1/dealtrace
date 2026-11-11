import json
from pathlib import Path
from .models import DateInterval, Guidance, money
from datetime import date

ROOT = Path(__file__).resolve().parent


def companies():
    return {c['ticker']: c for c in json.loads((ROOT / 'companies.json').read_text())}


def load_guidance(ticker):
    data = json.loads((ROOT / 'guidance' / f'{ticker}.json').read_text(), parse_float=money)
    records = []
    for row in data['versions']:
        source = row['source']
        g = Guidance(ticker, DateInterval.read(row['issued_date']), date.fromisoformat(row['filed_date']),
                     date.fromisoformat(row['fiscal_period']['start']), date.fromisoformat(row['fiscal_period']['end']),
                     row['low'], row['high'], row['currency'], row['basis'], row['status'],
                     source['accession'], source['exhibit'], source['url'], row['quote'],
                     row['metric'], row.get('original_verified', False), row.get('notes', ''))
        if not g.source_url.startswith('https://www.sec.gov/Archives/'):
            raise ValueError('Financial guidance requires an SEC source')
        if g.status == 'reaffirmed' and records and (g.low, g.high) != (records[-1].low, records[-1].high):
            raise ValueError('Reaffirmation cannot change the previous range')
        records.append(g)
    return records
