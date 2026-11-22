"""Recheck curated historical evidence against SEC sources, not an extractor."""
import argparse,json,re
from datetime import datetime,timezone
from decimal import Decimal
from bs4 import BeautifulSoup
from . import history,store
from .sec import fetch
from .models import dumps


def normalized(body):
    return ' '.join(BeautifulSoup(body,'html.parser').get_text(' ',strip=True).split())


def verify(row):
    source=row['source_record'];checks=[]
    for g in source['guidance_versions']:
        body,manifest=fetch(g['source_url']);text=normalized(body)
        check=next(c for c in source['guidance_source_checks'] if c['guidance_id']==g['id'])
        assert manifest['sha256']==check['source_sha256'],'guidance source hash changed'
        assert ' '.join(g['quote'].split()) in text,'guidance quote missing'
        issued_body,_=fetch(check.get('issuance_date_source_url',g['source_url']))
        assert check['issuance_date_quote'] in normalized(issued_body),'issuance date quote missing'
        assert history.guidance_record(row['company'],g).id==g['id'],'guidance ID mismatch'
        checks.append(g['id'])
    result=source['result'];body,m=fetch(result['source_url']);text=normalized(body)
    assert m['sha256']==result['source_sha256'],'result source hash changed'
    assert result['reported_revenue_quote'] in text and result['date_quote'] in text,'result quote missing'
    numbers=re.findall(r'\d[\d,]*(?:\.\d+)?',result['reported_revenue_quote'])
    reported=Decimal(numbers[result['column_index']].replace(',',''))*Decimal(result['unit_scale'])
    actual=store.actual_from({k:v for k,v in source['actual'].items() if k!='id'})
    assert actual.id==row['actual_id'],'actual ID mismatch'
    assert actual.value==reported,'company release revenue discrepancy'
    if source['outcome_basis_review'].get('scope_evidence'):
        # Scope review spans the guidance release, results release and filing;
        # e.g. guidance's acquisition-inclusion statement belongs to its release.
        scope=[]
        for evidence in source['outcome_basis_review']['sources']:
            body,_=fetch(evidence['url'])
            soup=BeautifulSoup(body,'html.parser')
            for hidden in soup.find_all('ix:header'):hidden.decompose()
            scope.append(' '.join(soup.get_text(' ',strip=True).split()))
        for quote in source['outcome_basis_review']['scope_evidence']:
            assert any(quote in text for text in scope),'scope-review quote missing from reviewed SEC sources'
    raw=source['actual_parents'] if actual.parents else [source['actual']]
    for a in raw:
        body,_=fetch(a['source_url']);facts=json.loads(body)['facts']['us-gaap'][a['concept']]['units'][a['unit']]
        assert any(f.get('start')==a['start'] and f['end']==a['end'] and f['accn']==a['accession'] and f['filed']==a['filed'] and Decimal(str(f['val']))==Decimal(a['value']) for f in facts),'companyfacts input missing'
    if actual.parents:
        annual=max(raw,key=lambda a:a['end']);ytd=min(raw,key=lambda a:a['end'])
        assert annual['start']==ytd['start'] and annual['end']==str(actual.end)
        from datetime import date,timedelta
        assert date.fromisoformat(ytd['end'])+timedelta(days=1)==actual.start
        assert Decimal(annual['value'])-Decimal(ytd['value'])==actual.value
        assert len({(a['company'],a['unit'],a['basis'],a['concept']) for a in raw})==1
    return dict(observation_id=row['id'],company=row['company'],period_start=row['period_start'],period_end=row['period_end'],
        guidance_ids=checks,actual_id=actual.id,reported_revenue=str(reported),actual_revenue=str(actual.value),
        discrepancy='0',status=row['status'],outcome=row['outcome'],blocking_reasons=row['blocking_reasons'])


def run():
    return dict(checked_at=datetime.now(timezone.utc).isoformat(),verifier='Codex deterministic SEC source/identity/reconciliation audit v1',rows=[verify(r) for r in history.load_all()])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
    result=run()
    with open(args.output,'x') as stream:stream.write(dumps(result)+'\n')
    print(dumps({'quarters_verified':len(result['rows']),'output':args.output}))
