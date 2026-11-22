"""Pilot-only exact fact-boundary registration, not extraction-rule tuning.

No date inferred from gold labels. Resolve only exact original filing periods,
or monthly boundaries from a consistent original annual calendar. Unknown weekly
future bounds abstain. Frozen v2 runs in a separate process with restored globals.
"""
from contextlib import contextmanager
from datetime import date,timedelta
from calendar import monthrange
from decimal import Decimal
import copy,json
from earnings.models import record_id
from earnings.actuals import derive_q4,parse_companyfacts,Blocked
from .collect import CACHE_ROOT,read

CONCEPTS=('RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet','SalesRevenueGoodsNet')

def registration(c,manifest,cutoff):
    payload=read(CACHE_ROOT.parent/manifest['body']);available=payload.get('facts',{}).get('us-gaap',{})
    rankings=[]
    for concept in CONCEPTS:
        rows=available.get(concept,{}).get('units',{}).get('USD',[])
        ends={r['end'] for r in rows if r.get('start') and r.get('form') in ('10-Q','10-K') and r['filed']<=cutoff and r['end']>='2023-01-01'}
        rankings.append((len(ends),-CONCEPTS.index(concept),concept))
    _,_,concept=max(rankings)
    facts=parse_companyfacts({**c,'concept':concept,'basis':'US_GAAP_consolidated_reported'},payload)
    facts=[a for a in facts if str(a.filed)<=cutoff and a.unit=='USD']
    originals={}
    for a in sorted(facts,key=lambda a:(a.filed,a.accession,a.id)):
        if a.form not in ('10-K','10-Q') or not a.fiscal_year:continue
        # A comparative fact with fiscal labels inherited from a later filing
        # cannot define the current year/quarter's calendar.
        lag=(a.filed-a.end).days;days=(a.end-a.start).days+1
        if not 0<=lag<=110:continue
        if a.form=='10-K' and 350<=days<=380:key=(a.fiscal_year,None)
        elif a.form=='10-Q' and 80<=days<=110 and a.fiscal_period in ('Q1','Q2','Q3'):key=(a.fiscal_year,int(a.fiscal_period[-1]))
        else:continue
        originals.setdefault(key,a)
    for (year,q),annual in list(originals.items()):
        if q is not None:continue
        nine=[a for a in facts if a.start==annual.start and a.end<annual.end and a.fiscal_period=='Q3' and 260<=(a.end-a.start).days+1<=280 and a.filed<=annual.filed]
        if not nine:continue
        a=min(nine,key=lambda a:(a.filed,a.accession));kind='weeks' if (annual.end-annual.start).days+1 in (364,371) else 'months'
        try:originals[(year,4)]=derive_q4(annual,a,expected_ytd_end=a.end,expected_annual_end=annual.end,calendar=kind)
        except Blocked:continue
    boundaries={f'{y}:{q or "FY"}':{'start':str(a.start),'end':str(a.end),'id':a.id,'accession':a.accession,'filed':str(a.filed),'parents':list(a.parents)} for (y,q),a in originals.items()}
    for b in read(__import__('pathlib').Path(__file__).parent/'supplemental_boundaries.json')['boundaries']:
        if b['company']==c['ticker']:
            boundaries[f"{b['year']}:{b['quarter']}"]={k:b[k] for k in ('start','end','source_manifest','result_manifest','reason')}
    annuals=[(y,a) for (y,q),a in originals.items() if q is None and y>=2022]
    months=[(a.start.month,a.end.month,a.end.year-y) for y,a in annuals if a.start.day==1 and a.end.day==monthrange(a.end.year,a.end.month)[1] and (a.end-a.start).days+1 in (365,366)]
    policy=None
    if annuals and len(months)==len(annuals) and len(set(months))==1:
        sm,em,offset=months[0];policy={'kind':'months','start_month':sm,'end_month':em,'end_year_offset':offset}
    return {'company':c['ticker'],'concept':concept,'concept_selection':'maximum recent distinct USD revenue periods among fixed concepts; scope still requires source review','boundaries':boundaries,'monthly_policy':policy,'end_year_offsets':sorted({a.end.year-y for y,a in annuals}),'original_facts':[a.__dict__ for a in originals.values()],'all_versions_count':len(facts),'companyfacts_manifest':manifest}

def resolve(reg,year,q=None):
    exact=reg['boundaries'].get(f'{year}:{q or "FY"}')
    if exact:return exact['start'],exact['end']
    p=reg['monthly_policy']
    if not p:raise ValueError('UNKNOWN_EXACT_FISCAL_BOUNDARY')
    ey=year+p['end_year_offset'];em=p['end_month'];end=date(ey,em,monthrange(ey,em)[1]);start=date(ey if em==12 else ey-1,p['start_month'],1)
    if q:
        m=start.month+3*(q-1);start=date(start.year+(m-1)//12,(m-1)%12+1,1);n=start.month+3;end=date(start.year+(n-1)//12,(n-1)%12+1,1)-timedelta(days=1)
    return str(start),str(end)

@contextmanager
def adapter(registrations):
    from earnings.extraction.v2 import rules
    original_period,original_calendars=rules.period,rules.CALENDARS
    regs={r['company']:r for r in registrations};extended=copy.deepcopy(original_calendars);extended['version']='pilot-exact-fact-calendar-v1'
    for t,r in regs.items():extended['companies'][t]={'end_year_offset':r['end_year_offsets'][0] if len(r.get('end_year_offsets',[]))==1 else None,'unknown_offset':len(r.get('end_year_offsets',[]))!=1}
    def lookup(company,year,quarter=None):
        if company in regs:return resolve(regs[company],year,quarter)
        return original_period(company,year,quarter)
    rules.period=lookup;rules.CALENDARS=extended
    try:yield
    finally:rules.period=original_period;rules.CALENDARS=original_calendars
