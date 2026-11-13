"""Manual period-inventory completion; does not rerun or change extraction.

Eight initially unresolved inventory dates are source/fact reconciliations only.
The original automated inventory and the first extraction evaluation stay intact.
"""
from datetime import datetime,timezone,timedelta,date
from copy import deepcopy
from earnings.models import plain
from earnings.extraction.corpus import canonical
from .collect import ROOT,read,write
from .review import raw
from .calendar import resolve
from .assemble import facts,actual_for

# Fixed manual reading of exact quarterly result headings, not parser outputs.
MAPPINGS={'JBL:0001628280-26-019043':(2026,3),'JBL:0001628280-25-057488':(2026,2),'JBL:0001628280-25-042693':(2026,1),'JBL:0001628280-25-014001':(2025,3),'JBL:0001628280-24-051805':(2025,2),'JBL:0001193125-24-226499':(2025,1),'SANM:0000897723-26-000036':(2026,4),'PLXS:0000785786-26-000049':(2026,4)}

def run():
    if (ROOT/'coverage_reviewed.json').exists():raise ValueError('Preserve existing reviewed coverage version')
    original=read(ROOT/'coverage.json');rows=deepcopy(original['rows']);groups={g['id']:g for g in read(ROOT/'inventory.json')['groups']};regs={r['company']:r for r in read(ROOT/'calendars.json')['registrations']};cs={c['ticker']:c for c in read(ROOT/'companies.json')['companies']};supp=[]
    for row in rows:
        if row['target_period']:continue
        y,q=MAPPINGS[row['group_id']];company=row['company'];reg=regs[company];g=groups[row['group_id']];e=g['result']['exhibits'][0];text=canonical(raw(e['manifest']));start,end=None,None
        if company=='JBL':
            start,end=resolve(reg,y,q);evidence=reg['boundaries'][f'{y}:{q}'];reason='Source heading identifies fiscal quarter/year; exact original10-Q monthly bounds independently match it. Headline omitted physical end date, so generic date matching abstained.'
        else:
            prior=reg['boundaries'][f'{y}:3'];start=str(date.fromisoformat(prior['end'])+timedelta(days=1));end='2026-10-03';evidence={'preceding_quarter':prior,'reported_end_quote':text[:750]};reason='Explicit result dateline gives Q4 endOctober3,2026; previous original Q3 fact gives preceding end. SANM Q4 is98days, PLXS Q4 is91days. Fiscal-week difference preserved, no amount derived from an incompatible nine-month duration.'
        fiscal={'fiscal_label':f'{y}:{q}','start':start,'end':end,'boundary_evidence':evidence};a,gap=actual_for(facts(cs[company],reg,original['cutoff']),start,end)
        item={'group_id':row['group_id'],'company':company,'target_period':fiscal,'source_url':e['source_url'],'source_manifest':e['manifest'],'quote':text[:750],'reason':reason,'reviewer':'Codex source curator','reviewed_at':datetime.now(timezone.utc).isoformat(),'use':'period inventory only, not extractor rules/gold, production or live inputs'};supp.append(item)
        row.update(target_period=fiscal,actual_id=a.id if a else None,actual_accession=a.accession if a else None,actual_filed=str(a.filed) if a else None,actual_value=str(a.value) if a else None,actual_gap=gap,manual_period_inventory_review=item)
    write(ROOT/'period_inventory_supplements.json',{'evidence':supp});write(ROOT/'coverage_reviewed.json',{'cutoff':original['cutoff'],'original':'coverage.json retained unchanged','scope':'source/fact inventory completions only; no candidate rerun or manual outcome approvals','rows':rows})
    print('Reviewed inventory:',len(rows),'mapped;',sum(r['actual_id'] is not None for r in rows),'raw actuals, not verified outcome count')

if __name__=='__main__':run()
