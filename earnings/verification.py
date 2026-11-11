"""Independent statement-column reconciliation for the two initial SEC examples."""
from datetime import date
from decimal import Decimal
import json
import re
from bs4 import BeautifulSoup
from .actuals import parse_companyfacts, snapshot, exactly
from .engine import hurdle
from .models import plain
from .registry import ROOT, companies, load_guidance
from .sec import fetch


def check_statement_columns(gold):
    expected=[(gold['expected_ytd'],gold['expected_prior_ytd']), (gold['expected_prior_annual'],None)]
    for evidence,(current,prior) in zip(gold['statement_evidence'],expected):
        numbers=[Decimal(n.replace(',',''))*Decimal(1000) for n in re.findall(r'\d[\d,]*',evidence['quote'])]
        if len(numbers)!=4 or numbers[2]!=Decimal(current) or (prior is not None and numbers[3]!=Decimal(prior)):
            raise ValueError('Statement column/scale reconciliation failed')


def verify_real(ticker):
    gold=json.loads((ROOT/'reconciliation.json').read_text())[ticker]
    check_statement_columns(gold)
    documents=[]
    for evidence in gold['statement_evidence']:
        body,m=fetch(evidence['source_url'])
        text=BeautifulSoup(body,'html.parser').get_text(' ',strip=True)
        if ' '.join(evidence['quote'].split()) not in ' '.join(text.split()):
            raise ValueError('Reported statement quote is not present at SEC source')
        documents.append({**evidence,'sha256':m['sha256']})
    c=companies()[ticker];cutoff=date(2026,11,11)
    body,m=fetch(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{c["cik"]}.json')
    actuals=parse_companyfacts(c,json.loads(body,parse_float=Decimal));history=load_guidance(ticker)
    r=hurdle(c,actuals,history,cutoff)
    if r.state!='ok' or r.remaining_low!=Decimal(gold['expected_remaining_low']) or r.remaining_high!=Decimal(gold['expected_remaining_high']):
        raise ValueError('Live SEC facts no longer reconcile to reviewed example at cutoff')
    by_id={a.id:a for a in actuals}
    return {'company':ticker,'as_of':str(cutoff),'companyfacts_manifest':m,
        'statement_evidence':documents,'calculation':{'id':r.id,'state':r.state,**plain(r)},
        'input_records':{role:{'id':identifier,**plain(by_id[identifier])} for role,identifier in r.inputs.items() if identifier in by_id},
        'guidance':{'id':history[-1].id,**plain(history[-1])}}
