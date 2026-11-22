"""Exact fiscal-period coverage from source dates and registered fact boundaries.

Date matching is only an inventory aid. It never establishes guidance or outcome
comparability and cannot approve a candidate for production/training.
"""
import re
from datetime import date
from earnings.extraction.corpus import canonical
from earnings.extraction.rules import DATE,MONTH
from .collect import ROOT,CACHE_ROOT,read,write
from .review import raw
from .assemble import actual_for,facts

def run():
    regs={r['company']:r for r in read(ROOT/'calendars.json')['registrations']};cs={c['ticker']:c for c in read(ROOT/'companies.json')['companies']};out=[]
    fc={t:facts(cs[t],r,read(ROOT/'plan.json')['cutoff']) for t,r in regs.items()}
    for g in read(ROOT/'inventory.json')['groups']:
        text=canonical(raw(g['result']['exhibits'][0]['manifest']));head=text[:3500];dates=set()
        for m in DATE.finditer(head):
            try:dates.add(str(date(int(m[3]),MONTH[m[1][:3].lower()],int(m[2]))))
            except ValueError:continue
        options=[(key,b) for key,b in regs[g['company']]['boundaries'].items() if not key.endswith(':FY') and b['end'] in dates and b['end']<g['result']['filed']]
        if options:
            end=max(b['end'] for key,b in options);choices=[(key,b) for key,b in options if b['end']==end]
            if len({(b['start'],b['end']) for key,b in choices})!=1:choices=[]
        else:choices=[]
        fiscal=None;actual=None;gap='UNRESOLVED_REPORTED_QUARTER_BOUNDARIES'
        if choices:
            key,b=choices[0];fiscal={'fiscal_label':key,'start':b['start'],'end':b['end'],'boundary_evidence':b};actual,gap=actual_for(fc[g['company']],b['start'],b['end'])
        out.append({'group_id':g['id'],'company':g['company'],'target_period':fiscal,'actual_id':actual.id if actual else None,'actual_accession':actual.accession if actual else None,'actual_filed':str(actual.filed) if actual else None,'actual_value':str(actual.value) if actual else None,'actual_gap':gap,'source_url':g['guidance_source_url'],'result_source':g['result']['exhibits'][0]['source_url'],'guidance_filed':g['source']['filed'],'result_filed':g['result']['filed'],'review_status':'PROVISIONAL_INVENTORY; see separate manual sample result_reviews for approved scope checks'})
    write(ROOT/'coverage.json',{'cutoff':read(ROOT/'plan.json')['cutoff'],'rows':out});return out

if __name__=='__main__':run()
