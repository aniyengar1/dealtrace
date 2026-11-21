"""Offline source inspection aids; never eligible labels or live data ingestion."""
import json,re
from pathlib import Path
from datetime import date,timedelta
from decimal import Decimal
from .scaling_2027q1_sources import ROOT,save
CONCEPTS=('RevenueFromContractWithCustomerExcludingAssessedTax','RevenueFromContractWithCustomerIncludingAssessedTax','Revenues','SalesRevenueNet')

def days(start,end):return (date.fromisoformat(end)-date.fromisoformat(start)).days+1

def actual_candidates(facts,event):
    issued=date.fromisoformat(event['report_date'] or event['filed']);cutoff=date(2026,11,20);raw=[]
    for concept in CONCEPTS:
        for f in facts.get('facts',{}).get('us-gaap',{}).get(concept,{}).get('units',{}).get('USD',[]):
            if not f.get('start') or f.get('form') not in ('10-K','10-Q','10-K/A','10-Q/A') or date.fromisoformat(f['filed'])>cutoff:continue
            lag=(issued-date.fromisoformat(f['end'])).days
            if 0<=lag<=100 and days(f['start'],f['end'])>=70:raw.append({'concept':concept,**f})
    if not raw:return []
    end=max(f['end'] for f in raw);candidates=[]
    for concept in CONCEPTS:
        same=[f for f in raw if f['concept']==concept and f['end']==end]
        for f in same:
            n=days(f['start'],end)
            if 80<=n<=100:candidates.append({'concept':concept,'start':f['start'],'end':end,'value':str(f['val']),'filed':f['filed'],'accession':f['accn'],'derivation':None,'parents':[]})
            elif 350<=n<=380:
                # Explicit compatible period boundaries, no calendar-quarter inference.
                allfacts=facts['facts']['us-gaap'][concept]['units']['USD']
                for y in allfacts:
                    if y.get('start')!=f['start'] or not y.get('end') or not y.get('filed') or y['filed']>str(cutoff):continue
                    yd=days(y['start'],y['end']);qd=(date.fromisoformat(end)-date.fromisoformat(y['end'])).days
                    weeks=(n in (364,371) and yd in (273,280) and qd in (91,98));months=(n in (365,366) and 89<=qd<=92 and 270<=yd<=276)
                    if not(weeks or months):continue
                    candidates.append({'concept':concept,'start':str(date.fromisoformat(y['end'])+timedelta(days=1)),'end':end,'value':str(Decimal(str(f['val']))-Decimal(str(y['val']))),'filed':max(f['filed'],y['filed']),'accession':f['accn'],'derivation':'annual-minus-nine-month-research','calendar':'weeks' if weeks else 'months','parents':[f,y]})
    # First available source vintage for each exact value/period/concept, preserving alternatives.
    unique={}
    for f in sorted(candidates,key=lambda f:(f['filed'],f['accession'])):
        if (date.fromisoformat(f['filed'])-issued).days>80:continue
        unique.setdefault((f['concept'],f['start'],f['end'],f['value']),f)
    return list(unique.values())

def aids(text):
    out=[]
    # Broad locators only: keep semantic alternatives, headings and units. No
    # resulting range/status is accepted from these substring matches.
    for m in re.finditer(r'(?:revenues?|net sales|total sales)\b',text,re.I):
        q=text[max(0,m.start()-220):m.start()+500]
        if re.search(r'\$\s*[\d,.]+.{0,45}(?:\bto\b|\+/-|[-–±]|plus or minus).{0,30}[\d,.]+',q,re.I) and re.search(r'guidance|outlook|expect|forecast|quarter|Q[1-4]|Low|High',q,re.I):
            out.append({'offset':max(0,m.start()-220),'quote':q})
    return out

MONTHS={m.lower():i for i,m in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}
DATE_RX=re.compile(r'\b('+'|'.join(MONTHS)+r'|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})',re.I)
def source_issue(doc,filing):
    candidates=[]
    for m in DATE_RX.finditer(doc['text'][:1800]):
        mon=m[1].lower().rstrip('.')
        month=MONTHS.get(mon) or next((v for k,v in MONTHS.items() if k.startswith(mon[:3])),None)
        try:day=date(int(m[3]),month,int(m[2]))
        except (ValueError,TypeError):continue
        if 0<=(date.fromisoformat(filing['filed'])-day).days<=7:
            candidates.append({'date':str(day),'quote':doc['text'][max(0,m.start()-90):m.end()+160]})
    # This is a date locator, not an invented issuance day. Ambiguity remains in
    # the packet and is checked during source curation; filing/reportDate alone
    # is never treated as the release dateline.
    return max(candidates,key=lambda x:x['date']) if candidates else None

def main():
    for inv in sorted(ROOT.glob('*/inventory.json')):
        try:
            d=json.loads(inv.read_text());m=d['companyfacts_source']['manifest'];facts=json.loads((Path('data/cache/earnings')/m['body']).read_text(),parse_float=Decimal);p=[]
            all_events=[]
            for descriptor in d['filings']:
                if '2.02' not in descriptor['items']:continue
                f0=json.loads(Path(descriptor['file']).read_text())
                e={k:f0[k] for k in ('accession','filed','report_date')}
                filings=[f0]
                docs=[];regular=False;issues=[]
                for f in filings:
                    for a in f['exhibits']:
                        if 'text' not in a:continue
                        h=a['text'][:2000]
                        positive=re.search(r'(?:reports?|announces?).{0,120}(?:quarter|fiscal).{0,120}(?:results|earnings)|(?:reports?|announces?).{0,80}(?:financial )?results.{0,100}(?:quarter|fiscal)|(?:quarter|Q[1-4]).{0,160}shareholder letter|shareholder letter.{0,160}(?:quarter|Q[1-4])',h,re.I)
                        negative=re.search(r'preliminary|business update|updated guidance|investor day|transcript|conference call|earnings call',h[:220],re.I)
                        primary_text=f['primary'].get('text','')
                        primary_letter=bool(re.search(r'(?:shareholder letter).{0,220}(?:financial results)|(?:financial results).{0,220}shareholder letter',primary_text,re.I)) and not re.search('preliminary',primary_text,re.I)
                        is_regular=bool((positive or primary_letter) and not negative)
                        regular=regular or is_regular
                        issued=source_issue(a,f)
                        if is_regular and issued:issues.append(issued)
                        docs.append({'url':a['url'],'sha256':a['manifest']['sha256'],'accession':f['accession'],'filed':f['filed'],'header':h[:650],'regular_result_header':is_regular,'issuance_locator':issued,'guidance_inspection_aids':aids(a['text'])})
                if regular and not issues:
                    issues=[z for f in filings if (z:=source_issue(f['primary'],f))]
                event={**e}
                if issues:
                    issue=max(issues,key=lambda x:x['date']);event.update(report_date=issue['date'],issuance_date_evidence=issue,original_8k_report_date=e['report_date'])
                all_events.append({'event':event,'actual_candidates':actual_candidates(facts,event),'documents':docs,'regular_result_event':regular})
            regular_events=sorted([e for e in all_events if e['regular_result_event']],key=lambda e:e['event']['report_date'],reverse=True)
            unique={}
            for e in regular_events:
                # Same release date/quarter is one observation, regardless of
                # the 8-K's unrelated earliest-event date or number of exhibits.
                end=max((a['end'] for a in e['actual_candidates']),default='unknown')
                key=(e['event']['report_date'],end)
                if key not in unique:unique[key]=e
                else:unique[key]['documents'].extend(e['documents'])
            regular_events=list(unique.values())
            # Earlier dated preliminary/in-line publications remain explicit
            # exclusions; do not silently treat them as extra fiscal quarters.
            for e in regular_events:
                ends={a['end'] for a in e['actual_candidates']}
                e['earlier_possible_publications']=[x['event'] for x in all_events if x['event']['report_date']<e['event']['report_date'] and not x['regular_result_event'] and ends & {a['end'] for a in x['actual_candidates']}]
            p=regular_events[:10]
            save(inv.parent/'inspection-packet.json',{'company':d['company'],'purpose':'locators and unreviewed fact candidates only; not usable-quarter counts','events':p,'all_events':all_events,'regular_event_count':len(regular_events),'inventory_selection_definition':d['selection_definition']})
        except (OSError,KeyError) as exc:print(inv.parent.name,'PACKET_SOURCE_GAP',type(exc).__name__,str(exc),flush=True)
if __name__=='__main__':main()
