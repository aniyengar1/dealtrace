"""Seal manually inspected result-table reconciliations, separately from gold.

No extractor tuning or production/ledger writes. Any scope decision here applies
only to the sampled target/result, never automatically to prior-year growth.
"""
from datetime import datetime,timezone
from decimal import Decimal
from earnings.models import record_id
from earnings.extraction.corpus import canonical
from .collect import ROOT,CACHE_ROOT,read,write
from .review import raw

BLOCKS={1:('Q4_DERIVATION_CALENDAR_UNSUPPORTED','FY2024 is 53 weeks with 280-day nine-month YTD and 91-day Q4. Existing protected derive_q4 requires273-day YTD. Press release reports2443205000USD; no compatible direct companyfact found. Clear by separately reviewed fiscal-week derivation support and parent reconciliation; do not alter protected prediction code in this pilot.'),6:('MISSING_COMPANYFACT_AT_CUTOFF','Nov12,2026 results report10409millionUSD, but annual10-K/companyfacts input is unavailable at cutoff. Clear by original annual filing and compatible nine-month parent or direct quarter fact; retain filing availability.'),19:('ACQUISITION_TARGET_SCOPE_MISMATCH','Guidance explicitly excludes Eucalyptus; Q2 result says Eucalyptus closed in June and reports753214000USD consolidated including it. Require separately evidenced comparable revenue excluding the acquisition, or explicit company comparable-scope confirmation. Do not equate Rest-of-World revenue with acquisition contribution.'),23:('SOURCE_FACT_SCALE_MISMATCH','Original selected companyfact says1018308USD; release table says1018308 in THOUSANDS, i.e.1018308000USD. Difference -99.9%. Do not multiply automatically. Require corrected XBRL/source scale evidence and a separately reviewed actual version.'),26:('PURCHASE_ACCOUNTING_REVENUE_EFFECT_UNRESOLVED','Guidance excludes purchase-accounting effects from Catapult. Reported revenue629369000USD reconciles numerically; release discusses goodwill impairment and compares revenue to guidance qualitatively but does not establish an exact purchase-accounting-neutral revenue amount. Require evidence that revenue impact is nil or a direct compatible figure. This is a target-result scope question, not a prior-year growth block.')}

def run():
    if (ROOT/'result_reviews.json').exists():raise ValueError('Append a new reviewed version instead of overwriting')
    packet=read(CACHE_ROOT/'result-review-packet.json');gs={g['sample_index']:g for g in read(ROOT/'gold.json')['records'] if g['metric']=='quarterly_consolidated_revenue'};sample=read(ROOT/'sample.json')['groups'];out=[]
    for r in packet['reviews']:
        i=r['sample_index'];g=gs[i];source=sample[i]['result']['exhibits'][0];text=canonical(raw(source['manifest']))
        if i in (10,21):
            anchor='Net sales $ 7,561.7' if i==10 else 'Net sales $1,484.7';a=text.index(anchor)
            r['table_windows']=[{'quote':text[max(0,a-230):a+650],'token':'7,561.7' if i==10 else '1,484.7','scale':'1000000'}]
        if i==23:r['reported_value']='1018308000'
        if i==1:r['reported_value']='2443205000'
        if i==6:r['reported_value']='10409000000'
        block=BLOCKS.get(i)
        r['reviewer']='Codex single source curator';r['reviewed_at']=datetime.now(timezone.utc).isoformat();r['growth_comparability']='NOT_REVIEWED; independent decision, no growth calculation used'
        if block:
            r['block'],r['block_detail']=block;r['outcome']=None;r['guidance_to_result_comparability']='UNRESOLVED_OR_INCOMPARABLE' if i in (19,26) else 'INPUT_BLOCK; no forced outcome'
        else:
            if not r['actual'] or not r['table_windows']:raise ValueError(f'No exact reconciliation {i}')
            r['block']=None;r['block_detail']=None;r['guidance_to_result_comparability']='REVIEWED_SAME_TARGET_REPORTED_SCOPE'
            r['scope_review']='Same consolidated reported quarter and revenue/sales label in guidance and result; exact original fact reconciles to reported table. No acquisition or week normalization performed; no assertion about prior-year growth. Single-curator scope check, not exhaustive acquisition due diligence.'
            if i==10:r['scope_review']+=' Original2024 companyfact maps to NET SALES7561.7m, not total revenue7568.2m; retain original Family Dollar scope, not later discontinued-operation comparatives.'
            if i==25:r['scope_review']+=' Both guidance and result expressly relate to continuing operations excluding UK; no recast performed.'
            if i==27:r['scope_review']+=' Guidance anticipates UpLift, result is reported total company revenue; acquisition existence alone does not block target-result comparison.'
            value=Decimal(r['actual']['value']);lo=Decimal(g['low']);hi=Decimal(g['high']);r['outcome']='below' if value<lo else 'above' if value>hi else 'within';r['reconciliation_difference']='0';r['reported_value']=str(value)
        r['id']=record_id('pilot-result-review-v1',r);out.append(r)
    write(ROOT/'result_reviews.json',{'reviewed_at':datetime.now(timezone.utc).isoformat(),'limitations':'Sample-only retrospective audit. Gold input is never production guidance; no live predictions. 130 other groups have no manual result-basis approval. Five sampled comparisons remain blocked, including three numeric/source-availability issues and two target-scope issues.','reviews':out})
    print('Reviewed',len(out),'quarter targets;',sum(r['block'] is None for r in out),'reconciled outcomes;',sum(r['block'] is not None for r in out),'blocked')

if __name__=='__main__':run()
