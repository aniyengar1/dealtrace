"""Serialize manual source transcriptions; never imports any extraction rules.

Not an automatic annotator. transcriptions.json contains the curator's manually
reviewed values, statuses and negative labels, fixed before extractor evaluation.
"""
import hashlib,re
from datetime import date,datetime,timezone
from decimal import Decimal
from .collect import ROOT,CACHE_ROOT,read,write
from .calendar import registration,resolve
from .review import raw
from earnings.extraction.corpus import canonical
from earnings.models import record_id

ANCHORS={0:'Full Year 2025 and Q3 Outlook',1:'Outlook for the Fourth',2:'Outlook for the Third',3:'Outlook for the Third',4:'Business Outlook',5:'Business Outlook',6:'Business Outlook',7:'Financial Outlook',8:'Fiscal Year 2025 Outlook',9:'Fiscal Year 2025 Financial Guidance',10:'Fiscal 2024 Outlook',11:'Guidance The company',12:'Guidance The company',13:'Financial Outlook',14:'Outlook:',15:'Outlook:',16:'Financial Outlook',17:'Financial Outlook',18:'Financial Outlook',19:'Financial Outlook',20:'Fourth Quarter of Fiscal Year 2025 Outlook',21:'Outlook: The following',22:'Business Outlook',23:'Initiates fiscal third quarter 2025 revenue guidance',24:'Outlook The following',25:'Financial Outlook',26:'Financial Outlook',27:'Financial Outlook',28:'Financial Outlook:',29:'Financial Outlook'}
FORMATS={0:'narrative-revenue',1:'narrative-USD-tolerance',2:'narrative-USD-tolerance',3:'narrative-USD-tolerance',4:'table-USD-tolerance',5:'table-USD-tolerance',6:'table-USD-tolerance',7:'bullet-revenue',8:'bullet-sales',9:'bullet-total-and-segments',10:'narrative-net-sales',11:'period-ending-table',12:'period-ending-table',13:'bullet-revenue',14:'bullet-sales',15:'bullet-sales',16:'bullet-revenue',17:'bullet-revenue',18:'bullet-revenue',19:'bullet-revenue',20:'bullet-revenue-and-point',21:'net-sales-table-footnote-period',22:'table-USD-tolerance',23:'mixed-actual-prior-target-table',24:'narrative-period-ending',25:'quarter-label-table',26:'ordinal-quarter-table',27:'ordinal-quarter-table',28:'reported-and-CC-prose',29:'bullet-revenue'}
# Literal prior-source tokens manually verified during source-only curation.
PRIOR={0:('6.68','6.76'),7:('780.0','790.0'),8:('1.874','1.907'),10:('31.0','32.0'),12:('3,189','3,201'),13:('1.451','1.457'),15:('4.33','4.42'),16:('1.37','1.40'),18:('2.3','2.4'),19:('2.7','2.9'),20:('27.9',),25:('1.28','1.33'),27:('2,468','2,576'),29:('2.640','2.654')}

def run():
    if (ROOT/'gold_seal.json').exists():raise ValueError('Gold already sealed; do not overwrite')
    sample=read(ROOT/'sample.json')['groups'];trans=read(ROOT/'transcriptions.json');cs=read(ROOT/'companies.json')['companies'];regs={c['ticker']:registration(c,read(CACHE_ROOT/(c['ticker']+'-collection.json'))['companyfacts'],'2026-11-12') for c in cs}
    write(ROOT/'calendars.json',{'version':'pilot-exact-fact-calendar-v1','registrations':list(regs.values())})
    reviews=[]
    for i,g in enumerate(sample):
        src=g['source'];e=src['exhibits'][0];text=canonical(raw(e['manifest']));a=text.find(ANCHORS[i]);assert a>=0,(i,ANCHORS[i]);b=min(len(text),a+3600)
        prior_evidence=None
        if i in PRIOR:
            earlier=sorted([r for r in read(CACHE_ROOT/(g['company']+'-collection.json'))['releases'] if r['filed']<src['filed']],key=lambda r:r['filed'],reverse=True)
            for r in earlier:
                et=canonical(raw(r['exhibits'][0]['manifest']))
                if all(v in et for v in PRIOR[i]):
                    at=et.find(PRIOR[i][0]);prior_evidence={'accession':r['accession'],'filed':r['filed'],'source_url':r['exhibits'][0]['source_url'],'source_manifest':r['exhibits'][0]['manifest'],'quote':et[max(0,at-180):at+450],'tokens':PRIOR[i]};break
            if not prior_evidence:raise ValueError(f'Missing manually checked prior source {i}')
        issue=date.fromisoformat(src['filed']);month=issue.strftime('%B');pat=rf'(?i)\b(?:{month}|{month[:3]}\.?)\s+{issue.day},?\s+{issue.year}\b';matches=list(re.finditer(pat,text))
        if not matches:raise ValueError(f'No checked issuance evidence {i}')
        # Curator confirmed date is release dateline/call date with same-day
        # primary announcement; retain contexts for review, not file-date inference.
        m=matches[0];issuequote=text[max(0,m.start()-70):m.end()+180]
        reviews.append({'sample_index':i,'id':g['id'],'company':g['company'],'source_url':e['source_url'],'source_manifest':e['manifest'],'canonical_sha256':hashlib.sha256(text.encode()).hexdigest(),'format':FORMATS[i],'reviewer':trans['reviewer'],'reviewed_at':datetime.now(timezone.utc).isoformat(),'review_scope':'Entire relevant revenue guidance: headings, all metric rows, prose, footnotes and historical-reference columns; not limited to extractor hits','outputs_hidden_at_label_creation':True,'guidance_quote':text[a:b],'quote_start':a,'quote_end':b,'issuance_evidence':issuequote,'prior_status_evidence':prior_evidence,'negative_and_scope_notes':trans['negative_and_scope_notes'][str(i)],'target_result_comparability':'PENDING_REVIEW; not inherited from prior-year growth','prior_year_growth_comparability':'NOT_REVIEWED; not required for extraction accuracy'})
    records=[]
    for i,y,q,lo,hi,status in trans['rows']:
        g=sample[i];r=reviews[i];src=g['source'];start,end=resolve(regs[g['company']],y,q);basis='US_GAAP_consolidated_reported'
        if i==10:basis='US_GAAP_consolidated_net_sales'
        if i==19:basis='US_GAAP_consolidated_reported_excluding_Eucalyptus'
        if i==25:basis='US_GAAP_consolidated_continuing_operations'
        if i==26:basis='US_GAAP_consolidated_reported_excluding_purchase_accounting_effects'
        row={'company':g['company'],'metric':'quarterly_consolidated_revenue' if q else 'consolidated_revenue','fiscal_label':f'Q{q} FY{y}' if q else f'FY{y}','start':start,'end':end,'low':str(Decimal(lo)*Decimal(1000000)),'high':str(Decimal(hi)*Decimal(1000000)),'unit':'USD','basis':basis,'status':status,'issued':{'start':src['filed'],'end':src['filed'],'precision':'day'},'filed':src['filed'],'accession':src['accession'],'exhibit':'99.1','source_url':r['source_url'],'quote':r['guidance_quote'],'quote_start':r['quote_start'],'quote_end':r['quote_end'],'source_sha256':r['source_manifest']['sha256'],'format':r['format'],'original_verified':False,'status_semantics':'Quarter initial = first directly issued range in this release group, not exhaustive original-history claim; annual revisions manually compared with prior same-period revenue source','sample_index':i}
        if str(i) in trans['absolute_dollar_tolerances_millions']:
            base,delta=map(Decimal,trans['absolute_dollar_tolerances_millions'][str(i)]);assert Decimal(lo)==base-delta and Decimal(hi)==base+delta
            row['normalization']={'method':'explicit USD base minus/plus explicit USD tolerance','base_millions':str(base),'tolerance_millions':str(delta),'endpoints_verbatim':False}
        row['id']=record_id('pilot-manual-gold-v1',row);records.append(row)
    result={'created_at':datetime.now(timezone.utc).isoformat(),'reviewer':trans['reviewer'],'limitations':'Single curator, no second-human adjudication. Selection screen exposed latest releases; sampled overlap disclosed. All source review and gold sealed before any pilot extractor outputs. Calendar labels use original SEC fact boundaries plus two source-reviewed quarter-boundary supplements, not outputs. This is a pilot source audit, not a validated ML dataset.','records':records,'release_reviews':reviews,'sample_sha256':hashlib.sha256((ROOT/'sample.json').read_bytes()).hexdigest()}
    write(ROOT/'gold.json',result)
    write(ROOT/'gold_seal.json',{'sealed_at':datetime.now(timezone.utc).isoformat(),'gold_sha256':hashlib.sha256((ROOT/'gold.json').read_bytes()).hexdigest(),'transcriptions_sha256':hashlib.sha256((ROOT/'transcriptions.json').read_bytes()).hexdigest(),'policy':'No candidate outputs viewed and no rules run on pilot before sealing. Do not tune frozen v2 against this sample.'})
    print('Sealed',len(records),'records in',len(reviews),'entire-release source reviews')

if __name__=='__main__':run()
