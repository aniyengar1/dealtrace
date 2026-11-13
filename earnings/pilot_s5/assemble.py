"""Quarantined company-quarter dataset with exact candidates/facts and blocks.

No automatic promotion, no baseline/ledger imports, no manufactured labels.
Comparability is NOT inferred from numeric equality or prior-year growth flags.
"""
from datetime import date
from decimal import Decimal
from earnings.actuals import parse_companyfacts,derive_q4,Blocked
from earnings.models import plain
from .collect import ROOT,CACHE_ROOT,read,write


def facts(c,reg,cutoff):
    payload=read(CACHE_ROOT.parent/reg['companyfacts_manifest']['body'])
    result=[a for a in parse_companyfacts({**c,'concept':reg['concept'],'basis':'US_GAAP_consolidated_reported'},payload) if str(a.filed)<=cutoff and a.unit=='USD']
    return result

def actual_for(candidates,start,end):
    exact=[a for a in candidates if str(a.start)==start and str(a.end)==end]
    if not exact:
        annuals=[a for a in candidates if str(a.end)==end and 350<=(a.end-a.start).days+1<=380]
        nine=[a for a in candidates if str(a.end)<start and (date.fromisoformat(start)-a.end).days==1 and 260<=(a.end-a.start).days+1<=280]
        derived=[]
        for annual in annuals:
            for ytd in nine:
                if ytd.start!=annual.start:continue
                try:derived.append(derive_q4(annual,ytd,expected_ytd_end=ytd.end,expected_annual_end=annual.end,calendar='weeks' if (annual.end-annual.start).days+1 in (364,371) else 'months'))
                except Blocked:continue
        exact=derived
    if not exact:return None,'MISSING_COMPATIBLE_QUARTER_ACTUAL'
    day=min(a.filed for a in exact);originals=[a for a in exact if a.filed==day]
    if len({a.value for a in originals})!=1:return None,'CONFLICTING_EARLIEST_FACT_VALUES'
    return min(originals,key=lambda a:(a.accession,a.id)),None

def run():
    inv=read(ROOT/'inventory.json');cs={c['ticker']:c for c in read(ROOT/'companies.json')['companies']};regs={r['company']:r for r in read(ROOT/'calendars.json')['registrations']};allc=read(CACHE_ROOT/'all-candidates.json');gold=read(ROOT/'gold.json');out=[]
    reviews={r['guidance_id']:r for r in read(ROOT/'result_reviews.json')['reviews']} if (ROOT/'result_reviews.json').exists() else {}
    cutoff=read(ROOT/'plan.json')['cutoff'];fc={t:facts(c,regs[t],cutoff) for t,c in cs.items()}
    for t,versions in fc.items():write(CACHE_ROOT/(t+'-actual-versions.json'),{'company':t,'concept':regs[t]['concept'],'cutoff':cutoff,'versions':[{**plain(a),'id':a.id} for a in versions]})
    for group in inv['groups']:
        url=group['guidance_source_url'];versions=[c for c in allc['candidates'] if c['source_url']==url and c['metric']=='quarterly_consolidated_revenue'];partials=[c for c in allc['partials'] if c['source_url']==url and c['metric']=='quarterly_consolidated_revenue'];labels=[g for g in gold['records'] if g['source_url']==url and g['metric']=='quarterly_consolidated_revenue'];rows=[]
        # Gold is audit evidence, never input to the candidate history/production.
        # A sampled miss stays a miss while preserving the correct manual label.
        targets=labels or versions or partials
        for target in targets:
            a,gap=actual_for(fc[group['company']],target['start'],target['end'])
            rows.append({'guidance_id':target['id'],'guidance_origin':'manual_audit_gold' if target in labels else 'quarantined_extractor','start':target['start'],'end':target['end'],'actual':{**plain(a),'id':a.id} if a else None,'actual_gap':gap,'outcome':None,'block':'UNREVIEWED_GUIDANCE_TO_RESULT_SCOPE','growth_comparability':'NOT_REVIEWED; independent of guidance-to-result basis','guidance_to_result_comparability':'PENDING_MANUAL_SOURCE_RECONCILIATION','guidance_versions':versions,'partials':partials})
        for row in rows:
            review=reviews.get(row['guidance_id'])
            if review:
                row.update({'outcome':review['outcome'],'block':review['block'],'block_detail':review['block_detail'],'guidance_to_result_comparability':review['guidance_to_result_comparability'],'result_review_id':review['id'],'label_use':'RETROSPECTIVE_MANUAL_AUDIT_ONLY; not production or live-lock input'})
            elif row['actual'] and row['actual']['filed']<=group['source']['filed']:
                row['block']='GUIDANCE_SOURCE_NOT_BEFORE_TARGET_RESULT';row['outcome']=None
        out.append({'group_id':group['id'],'company':group['company'],'guidance_filed':group['source']['filed'],'guidance_source':url,'result_filed':group['result']['filed'],'result_source':group['result']['exhibits'][0]['source_url'],'candidate_versions':versions,'review_partials':partials,'reviewed_gold_ids':[g['id'] for g in labels],'targets':rows,'block':None if rows else 'NO_ACCEPTED_QUARTERLY_CANDIDATE_OR_REVIEWED_TARGET','abstentions':[b for b in allc['abstentions'] if b['source_url']==url]})
    write(CACHE_ROOT/'dataset.json',{'cutoff':cutoff,'production':False,'rows':out});print('Quarantined',len(out),'company-quarter release groups')
    return out

if __name__=='__main__':run()
