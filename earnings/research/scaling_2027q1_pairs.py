"""Offline research inspection proposals. Not an extraction-quality evaluation.

Nothing is accepted or imported by this module. Exact source locations, alternate
ranges and unmatched periods are retained for agent source curation. Existing
production guidance, frozen extractors, baseline methods and ledger are untouched.
"""
import json,re
from datetime import date,timedelta
from decimal import Decimal
from pathlib import Path
from .scaling_2027q1_sources import ROOT,save
MONEY=re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*(billion|million|thousand|[BM])?',re.I)
AFTER=re.compile(r'^\s*,?\s*(plus or minus|\+/-|±|to|and|[-–])\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(billion|million|thousand|[BM]|%)?',re.I)
SCALES={'billion':Decimal('1000000000'),'b':Decimal('1000000000'),'million':Decimal('1000000'),'m':Decimal('1000000'),'thousand':Decimal('1000')}

def proposed_ranges(s):
    proposals=[]
    for m in re.finditer(r'\b(?:total\s+|net\s+)?(?:revenues?|sales)\b',s,re.I):
        before=s[max(0,m.start()-30):m.start()].lower()
        if re.search(r'product |subscription |segment |service |organic |constant.currency ',before[-20:]):continue
        tail=s[m.end():m.end()+150];money=MONEY.search(tail)
        if not money or re.search(r'\bARR\b|income|earnings|expenses|gross margin|per share',tail[:money.start()],re.I):continue
        op=AFTER.match(tail[money.end():]);kind=None
        if op:kind='tolerance' if op[1].lower() in ('plus or minus','+/-','±') else 'range'
        elif re.search(r'Low\s*(?:End)?\s+High\s*(?:End)?',s[max(0,m.start()-500):m.start()],re.I):
            op=re.match(r'^\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(billion|million|thousand|[BM])?',tail[money.end():],re.I)
            if op:kind='explicit_low_high_columns'
        if not kind:continue
        unit=money[2];second=op[2] if kind=='explicit_low_high_columns' else op[3];raw2=op[1] if kind=='explicit_low_high_columns' else op[2]
        context=s[max(0,m.start()-650):m.end()+260]
        if not re.search(r'outlook|guidance|expect|forecast|anticipat',context,re.I):continue
        scale1=SCALES.get((unit or (None if second=='%' else second) or '').lower());scale2=SCALES.get((second or unit or '').lower())
        if scale1 is None:
            # Explicit table-unit evidence only; never infer scale from magnitudes.
            header=s[max(0,m.start()-1300):m.end()+money.start()]
            units=list(re.finditer(r'\bin\s+(millions|thousands)\b',header,re.I))
            if units:scale1=SCALES[units[-1][1].lower().rstrip('s')];scale2=scale2 or scale1
        low=high=None
        if scale1 is not None and (scale2 is not None or second=='%'):
            a=Decimal(money[1].replace(',',''))*scale1;b=Decimal(raw2.replace(',',''))
            if kind=='tolerance':
                delta=a*b/Decimal('100') if second=='%' else b*(scale2 or scale1);low=a-delta;high=a+delta
            else:low=a;high=b*(scale2 or scale1)
        proposals.append({'mention_offset':m.start(),'kind':kind,'first_raw':money[0],'operator_and_second_raw':op[0],'low':str(low) if low is not None else None,'high':str(high) if high is not None else None,'context_offset':max(0,m.start()-650),'context':context,'scale_evidence':'explicit row unit or preceding table header' if scale1 is not None else 'UNRESOLVED','manual_status':'unreviewed'})
    return proposals

def actual_quote(s,a):
    hits=[]
    value=Decimal(a['value'])
    for m in re.finditer(r'\b(?:total\s+|net\s+)?(?:revenues?|sales)\b',s,re.I):
        tail=s[m.end():m.end()+170]
        nums=list(re.finditer(r'(?<![\w.])\d[\d,]*(?:\.\d+)?',tail))
        for n in nums[:3]:
            v=Decimal(n[0].replace(',',''))
            for scale in (Decimal(1),Decimal(1000),Decimal(1000000)):
                if v*scale==value:hits.append({'context_offset':max(0,m.start()-400),'context':s[max(0,m.start()-400):m.end()+250],'unit_scale':str(scale),'value_column_among_nearby_numbers':nums.index(n),'match_kind':'exact amount; semantic column/period review still required'})
    return hits

def build(t):
    root=ROOT/t;d=json.loads((root/'inspection-packet.json').read_text());out=[]
    for i,e in enumerate(d['events'][:8]):
        if i+1>=len(d['events']):continue
        previous=d['events'][i+1];docs=[];result_sources=[]
        for doc in previous['documents']:
            x=json.loads((root/(doc['accession']+'.json')).read_text());raw=next(a for a in x['exhibits'] if a['url']==doc['url']);rs=proposed_ranges(raw['text'])
            docs.append({'url':doc['url'],'sha256':doc['sha256'],'accession':doc['accession'],'filed':doc['filed'],'header':doc['header'],'range_proposals':rs})
        actuals=sorted(e['actual_candidates'],key=lambda a:(a['filed'],a['concept']))
        # Preserve all competing concepts/amounts. No implicit concept or restatement selection.
        for doc in e['documents']:
            x=json.loads((root/(doc['accession']+'.json')).read_text());raw=next(a for a in x['exhibits'] if a['url']==doc['url']);result_sources.append({'url':doc['url'],'sha256':doc['sha256'],'header':doc['header'],'actual_matches':[{'actual_index':j,'hits':actual_quote(raw['text'],a)} for j,a in enumerate(actuals)]})
        out.append({'result_event':e['event'],'preceding_event':previous['event'],'guidance_documents':docs,'actual_candidates':actuals,'result_documents':result_sources,'status':'MANUAL_RESEARCH_REVIEW_REQUIRED','earlier_possible_publications':e.get('earlier_possible_publications',[]),'selected_guidance_cutoff':str(date.fromisoformat(e['event']['report_date'])-timedelta(days=15))})
    save(root/'pair-proposals.json',{'company':t,'kind':'quarantined research locators, not usable observations','pairs':out})

def main():
    for inv in sorted(ROOT.glob('*/inspection-packet.json')):
        try:build(inv.parent.name)
        except (KeyError,OSError):continue
if __name__=='__main__':main()
