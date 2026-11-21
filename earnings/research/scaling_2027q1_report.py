"""Build a quarantined research audit from pinned SEC sources and source curation.

No database, prediction, extractor, or model imports. Does not fetch or promote.
Exact-match locators are evidence aids, not semantic validation. Manual selections
and unresolved evidence are retained alongside the deterministic checks.
"""
import hashlib,json,re
from collections import Counter
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
from .scaling_2027q1_sources import ROOT,save
BASE=Path('earnings/research/scaling_2027q1')
REPORT=Path('earnings/reports/scaling_lock_readiness_2027Q1')
M=Decimal('1000000')
# Source-curated exceptions, never silently selected from model/extractor output.
BLOCKS={('FORM',2):'PERIOD_MISMATCH: guidance explicitly ends March29,2026; SEC actual ends March28,2026. Need issuer calendar correction or reconciliation.',('LITE',5):'BASIS_REVIEW: June3 updated outlook labelled non-GAAP; establish revenue equivalence to GAAP result before using this version.',('AKAM',0):'ACQUISITION_SCOPE_REVIEW: September24 transaction disclosure references guidance effects; target-period basis impact not fully reconciled.',('LSCC',0):'ACQUISITION_SCOPE_REVIEW: guide includes approximately two months of AMI; reconcile actual acquisition contribution and included scope. FPGA-only range is not consolidated.'}
BLOCKS.pop(('AKAM',0))
BLOCKS.pop(('LSCC',0))
UPDATES={('PINS',2):('0001506293-26-000026','958','978','2026-02-18'),('MPWR',6):('0001437749-25-008519','630','640','2025-03-20'),('ONTO',3):('0001193125-25-283980','258','275','2025-11-17')}
REAFFIRM={('TENB',6):'0001660280-25-000013',('MPWR',2):'0001437749-26-006112',('MPWR',7):'0001437749-24-034352',('BL',6):'0001193125-25-044753',('KLAC',7):'0001193125-24-269393',('DOCN',3):'0001582961-25-000153',('ONTO',4):'0001193125-25-236464',('DOCS',2):'0001516513-26-000014',('AMPL',2):'0001193125-26-067137',('RPD',1):'0001193125-26-249850',('ENPH',7):'0001463101-24-000145'}
PRELIM={('TENB',7):'0001660280-25-000002',('MKSI',3):'0001193125-26-017468',('BL',7):'0001171843-25-000196',('ENPH',2):'0001463101-26-000037',('TWLO',7):'0001193125-25-011461',('DOCN',1):'0001582961-26-000055',('DOCN',6):'0001582961-25-000072',('ONTO',2):'0001193125-26-158081',('FIVN',6):'0001288847-25-000080',('ICHR',3):'0001652535-26-000004',('ICHR',7):'0001628280-25-001255'}
PRELIM.update({('MCHP',3):'0000827054-26-000002',('LITE',7):'0001193125-25-019371',('TDOC',4):'0001477449-25-000114'})
PRELIM.update({('DOCS',2):'0001516513-26-000014',('ONTO',4):'0001193125-25-236464'})

def canonical_doc(t,url,accession=None):
    paths=[ROOT/t/(accession+'.json')] if accession else list((ROOT/t).glob('*.json'))
    for p in paths:
        d=json.loads(p.read_text())
        if 'primary' not in d:continue
        for a in [d['primary']]+d.get('exhibits',[]):
            if a['url']==url:return a,d
    raise KeyError(url)

def evidence(a,f,quote):
    assert quote in a['text']
    return {'url':a['url'],'sha256':a['manifest']['sha256'],'retrieved_at':a['manifest']['fetched_at'],'accession':f['accession'],'filed':f['filed'],'quote':quote,'quote_offset':a['text'].index(quote)}

def source_range(t,i,p,expected):
    if expected.startswith('BLOCK_'):return None,expected
    lo,hi=[Decimal(x)*M for x in expected.split(':')]
    selected=[]
    for doc in p['guidance_documents']:
        for q in doc['range_proposals']:
            if q['low'] is not None and Decimal(q['low'])==lo and Decimal(q['high'])==hi:
                a,f=canonical_doc(t,doc['url'],doc['accession']);selected.append(evidence(a,f,q['context']))
    if not selected and t in ('DIOD','ICHR','HLIT','APP','TASK','SANM'):
        # Source-curated tables/tolerance arithmetic. Retain the full explicit
        # headers; do not sum segments or label derived ranges as directly quoted.
        for doc in p['guidance_documents']:
            a,f=canonical_doc(t,doc['url'],doc['accession']);s=a['text'];anchor=None
            patterns={'DIOD':r'(?:Business Outlook|[Bb]usiness outlook|[Oo]utlook).{0,1600}', 'ICHR':r'Financial Outlook.{0,1200}', 'HLIT':r'Q[1-4] 202[456] GAAP Financial Guidance.{0,1100}', 'APP':r'Guidance Summary.{0,900}', 'TASK':r'202[456] Outlook.{0,900}', 'SANM':r'Third Quarter Fiscal 2026 Outlook.{0,600}'}
            for m in re.finditer(patterns[t],s,re.S):
                q=m[0]
                nums=[Decimal(n.replace(',','')) for n in re.findall(r'(?<!\w)\d[\d,]*(?:\.\d+)?',q)]
                if t=='DIOD':
                    center=(lo+hi)/Decimal(2)/M
                    valid=center in nums and re.search(r'plus or minus\s*3\s*(?:percent|%)|\+/-\s*3\s*%',q,re.I)
                else:valid=(lo/M in nums and hi/M in nums) or (lo/Decimal('1000000000') in nums and hi/Decimal('1000000000') in nums)
                if valid:selected.append(evidence(a,f,q));break
    if not selected:return None,'GUIDANCE_SOURCE_SUPPORT_UNRESOLVED: selected amount/units/header not located; do not infer a range.'
    e=selected[0];e.update(low=str(lo),high=str(hi),currency='USD',basis='reported consolidated revenue; per-period source scope retained',issued=p['preceding_event']['report_date'],issuance_evidence=p['preceding_event'].get('issuance_date_evidence'),status='selected prior-results-release-to-next-quarter range; original/initial status not inferred')
    if (t,i) in UPDATES:
        accession,l,h,issued=UPDATES[t,i];f=json.loads((ROOT/t/(accession+'.json')).read_text());ds=[f['primary']]+f['exhibits'];a=next(a for a in ds if ('revenue guidance range' in a.get('text','').lower() or 'updating its first quarter' in a.get('text','').lower() or 'Previously Announced on February 6' in a.get('text','')));s=a['text'];m=re.search(r'updating its first quarter|updating its revenue|Previously Announced on February 6',s,re.I);q=s[max(0,m.start()-180):m.start()+700]
        e={'previous_range_evidence':e,**evidence(a,f,q),'low':str(Decimal(l)*M),'high':str(Decimal(h)*M),'currency':'USD','issued':issued,'basis':'reported consolidated revenue; acquisition-inclusive where explicitly stated','status':'updated as explicitly supported by source'}
    if (t,i) in REAFFIRM:
        f=json.loads((ROOT/t/(REAFFIRM[t,i]+'.json')).read_text());a=f['primary'];s=a['text'];m=re.search('reaffirm|remains unchanged|no changes|not result in any changes|materially impact its previously provided guidance',s,re.I)
        if m:e['subsequent_unchanged_version']=evidence(a,f,s[max(0,m.start()-180):m.start()+450])
    if t=='DIOD':
        repeats=['0001193125-26-345311','0001193125-26-219765','0001193125-26-048964','0001193125-25-277876','0001193125-25-178039','0000950170-25-069436','0000950170-25-021394','0000950170-24-125620']
        f=json.loads((ROOT/t/(repeats[i]+'.json')).read_text());raw=f['exhibits'][0];center=(lo+hi)/2/M
        m=next((m for m in re.finditer(r'revenue.{0,90}?\$([\d,.]+)\s*million.{0,35}?(?:plus or minus|\+/-)\s*3\s*%',raw['text'],re.I) if Decimal(m[1].replace(',',''))==center),None)
        if m:
            e['subsequent_same_range_source']=evidence(raw,f,raw['text'][max(0,m.start()-160):m.end()+180])
            e['selected_version_filed']=max(e['filed'],f['filed'])
            e['selected_version_accession']=f['accession']
        else:
            return e,'TRANSCRIPT_RANGE_REVIEW_UNRESOLVED: subsequent furnished outlook needs source comparison.'
    if t=='HLIT':e['basis']='GAAP consolidated continuing operations/Broadband; discontinued Video excluded' if i<=2 else 'GAAP consolidated Video and Broadband total as originally reported'
    if t=='PCTY':e['basis']='GAAP total consolidated revenue including interest on client funds; recurring-only revenue excluded'
    return e,None

def classify(v,lo,hi):return 'below' if v<lo else 'above' if v>hi else 'within'

def reconcile(t,p):
    alternatives=p['actual_candidates'];eligible=[]
    for j,a in enumerate(alternatives):
        # Explicit company concept selection; never take recurring revenue at PCTY.
        if t=='PCTY' and a['concept']!='Revenues':continue
        if t=='PLXS' and a['concept']!='RevenueFromContractWithCustomerIncludingAssessedTax':continue
        for doc in p['result_documents']:
            for match in doc['actual_matches']:
                if match['actual_index']!=j or not match['hits']:continue
                hit=match['hits'][0];raw,f=canonical_doc(t,doc['url']);eligible.append((a,evidence(raw,f,hit['context']),{'kind':'exact reported release amount × explicit reporting scale','scale':hit['unit_scale'],'difference_usd':'0'}));break
    if not eligible and t in ('COHR','AMPL'):
        for a in alternatives:
            for doc in p['result_documents']:
                raw,f=canonical_doc(t,doc['url']);s=raw['text']
                # These two release formats publish summary GAAP amounts in
                # millions. Preserve rounding, original XBRL and the discrepancy.
                anchor=s.find('GAAP Financial Results') if t=='COHR' else s.find('Financial Highlights: (in millions')
                if anchor<0:continue
                m=re.search(r'(?<!Recurring )\bRevenues?\s*\$\s*([\d,]+(?:\.\d+)?)',s[anchor:anchor+900])
                if not m:continue
                n=Decimal(m[1].replace(',',''));quantum=M/(Decimal(10)**max(0,-n.as_tuple().exponent));printed=n*M;diff=Decimal(a['value'])-printed
                if abs(diff)<=quantum/2:
                    q=s[max(0,anchor-200):anchor+min(1100,m.end()+250)];eligible.append((a,evidence(raw,f,q),{'kind':'explicit rounded GAAP release summary; XBRL amount preserved','printed_usd':str(printed),'rounding_quantum_usd':str(quantum),'difference_usd':str(diff)}))
    if not eligible:return None,None,None,'MISSING_COMPATIBLE_ACTUAL' if not alternatives else 'ACTUAL_RECONCILIATION_UNRESOLVED: no same-quarter exact release match or documented rounding match; alternatives preserved.'
    # Equal amounts across concepts are preserved, not combined. Different valid
    # amounts require source adjudication rather than arbitrary preference.
    values={(a['start'],a['end'],a['value']) for a,_,_ in eligible}
    if len(values)>1:return None,None,None,'AMBIGUOUS_ACTUAL: competing source-matched concepts/values require explicit selection.'
    return *eligible[0],None

def audit(t,ranges):
    d=json.loads((ROOT/t/'pair-proposals.json').read_text());rows=[]
    for i,p in enumerate(d['pairs'][:8]):
        guide,ge=source_range(t,i,p,ranges[i]);a,ae,recon,err=reconcile(t,p);blocks=[x for x in (ge,err,BLOCKS.get((t,i))) if x]
        if guide:
            if guide['issued']>p['selected_guidance_cutoff'] or guide['filed']>p['selected_guidance_cutoff']:blocks.append('LATE_GUIDANCE: issuance and SEC filing must both precede D−15 cutoff.')
            if 'subsequent_unchanged_version' in guide and guide['subsequent_unchanged_version']['filed']>p['selected_guidance_cutoff']:blocks.append('LATE_REAFFIRMATION')
        if (t,i) in PRELIM:blocks.append('EARLIER_COMPLETED_PERIOD_DISCLOSURE: '+PRELIM[t,i]+'; exclude under frozen historical policy, do not relabel as prospective.')
        elif p['earlier_possible_publications']:blocks.append('EARLIER_PUBLICATION_REVIEW: '+', '.join(x['accession'] for x in p['earlier_possible_publications']))
        if a and guide and recon.get('rounding_quantum_usd'):
            mid=Decimal(recon['printed_usd']);q=Decimal(recon['rounding_quantum_usd']);lo=Decimal(guide['low']);hi=Decimal(guide['high'])
            if classify(mid-q/2,lo,hi)!=classify(mid+q/2,lo,hi):blocks.append('ROUNDING_BOUNDARY_AMBIGUITY: source rounding interval crosses guidance endpoint.')
        result={'index':i,'result_release':p['result_event'],'historical_guidance_cutoff':p['selected_guidance_cutoff'],'guidance':guide,'actual':a,'actual_source':ae,'reconciliation':recon,'actual_alternatives':p['actual_candidates'],'result_sources':[{k:v for k,v in x.items() if k!='actual_matches'} for x in p['result_documents']],'blocks':blocks,'status':'BLOCKED' if blocks else 'SOURCE_MATCHED','outcome':classify(Decimal(a['value']),Decimal(guide['low']),Decimal(guide['high'])) if not blocks else None,'review_provenance':'Codex agent source curation, not owner human review; research only'}
        if guide:guide['research_version_id']=hashlib.sha256(json.dumps(guide,sort_keys=True).encode()).hexdigest()
        if a:a['unit']='USD'
        if a:a['research_fact_id']=hashlib.sha256(json.dumps(a,sort_keys=True).encode()).hexdigest()
        if t=='LSCC' and i==0:
            result['growth_comparability']='Not comparable without supported scope analysis: prior periods exclude AMI. Not used in this outcome classification.'
            result['guidance_to_result_comparability']='Comparable acquisition-inclusive scope: guide issued Aug4 after July27 close includes about two months of AMI; results explicitly include AMI from July27. No normalization.'
            result['scope_evidence']=[]
            for doc in p['guidance_documents'][:1]+p['result_documents'][:1]:
                raw,f=canonical_doc(t,doc['url']);m=re.search('Lattice Closes AMI Acquisition|Lattice completed the acquisition',raw['text']);q=raw['text'][max(0,m.start()-80):m.start()+650];result['scope_evidence'].append(evidence(raw,f,q))
        if t=='AKAM' and i==0:
            f=json.loads((ROOT/t/'0001193125-26-401048.json').read_text());raw=f['exhibits'][0];m=re.search('Akamai anticipates no impact',raw['text']);result['intervening_scope_review']=evidence(raw,f,raw['text'][m.start():m.start()+400]);result['guidance_to_result_comparability']='No entity-scope change identified; commercial commitment explicitly has no impact on 2026 revenue guidance. Not an acquisition block.'
        result['research_id']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest();rows.append(result)
    return rows

def build():
    manual=json.loads((BASE/'manual_ranges.json').read_text());ann=json.loads((BASE/'announcement_pairs.json').read_text())['pairs'];universe=json.loads(Path('earnings/reports/scaling_universe_2027Q1.json').read_text());companies=universe['companies'] if isinstance(universe,dict) and 'companies' in universe else universe
    # The pre-existing screen may contain non-R1 rows. Exact manual manifest is
    # the fixed 64-company population, not format-driven replacement sampling.
    lookup={c['ticker']:c for c in companies};out=[]
    for t,raw in manual['companies'].items():
        proposed=json.loads((ROOT/t/'pair-proposals.json').read_text())['pairs'][:8]
        anchors=[{'result_accession':p['result_event']['accession'],'result_release_date':p['result_event']['report_date'],'prior_guidance_accession':p['preceding_event']['accession']} for p in proposed]
        if anchors!=manual['selection_anchors'][t]:
            raise ValueError(f'{t}: source selection changed; fresh agent source review required')
        rows=audit(t,raw.split('|'));regular=json.loads((ROOT/t/'inspection-packet.json').read_text())['events'];last4=[e['event']['report_date'] for e in regular[:4]];pairs=[]
        for x in ann:
            if x['ticker']!=t:continue
            y={**x,'lead_days':(date.fromisoformat(x['scheduled_release'])-date.fromisoformat(x['issued'])).days,'in_last_four':x['scheduled_release'] in last4}
            if not y['in_last_four']:y['exclusion']='Not one of latest four SEC regular results releases, or announcement/release date mismatch.'
            pairs.append(y)
        matched={x['scheduled_release']:x for x in pairs if x['in_last_four']};leads=sorted(Decimal(x['lead_days']) for x in matched.values());median=(leads[(len(leads)-1)//2]+leads[len(leads)//2])/2 if leads else None
        prior=[e['event'] for e in regular if '2026-01-01'<=e['event']['report_date']<='2026-02-28'];expected=date.fromisoformat(prior[0]['report_date'])+timedelta(days=364) if len(prior)==1 else None
        opening=datetime.combine(expected-timedelta(days=17),datetime.min.time(),ZoneInfo('America/New_York')) if expected else None
        n=sum(r['status']=='SOURCE_MATCHED' for r in rows);complete=len(matched)==4
        tier='A' if n>=6 and complete else 'B' if n>=6 else 'C'
        inv=json.loads((ROOT/t/'inventory.json').read_text())
        dates_root=Path('data/cache/earnings/scaling-2027q1-dates')/t
        http_checks=[]
        for f in sorted(dates_root.glob('*.json')):
            try:z=json.loads(f.read_text())
            except (OSError,ValueError):continue
            if isinstance(z,dict) and z.get('url') and z.get('checked_at'):http_checks.append({k:z[k] for k in ('url','checked_at','fetched_at','http_status','status','error','sha256','redirects') if k in z})
        date_attempts={'official_http_checks':http_checks,'web_search_discovery_artifact':str(dates_root/'web-search-leads.txt'),'unverified_last_four_release_dates':[day for day in last4 if day not in matched],'call_only_exclusion':'RMBS announcements give call dates without separate publication evidence' if t=='RMBS' else None}
        out.append({'ticker':t,'company':lookup[t].get('name',lookup[t].get('company',t)),'cik':lookup[t]['cik'],'tier':tier,'source_matched_quarters':n,'quarters_audited':len(rows),'full_live_onboarding_review':'NOT_COMPLETE: no production import, owner approval, or future target/evidence acceptance; source-matched is not a live lock gate. Intervening SEC 8-K primary disclosures screened; non-8-K disclosures and full corporate-scope onboarding remain separate prerequisites.','quarter_rows':rows,'last_four_results_dates':last4,'announcement_pairs':pairs,'announcement_research_attempts':date_attempts,'verified_last_four_pairs':len(matched),'lead_days_median':str(median) if median is not None else None,'lead_range_days':[str(leads[0]),str(leads[-1])] if leads else None,'typical_last_four_gap':str(median) if complete else None,'date_gap':'Complete four-pair study' if complete else f'{len(matched)}/4 source-supported publication pairs; remaining official article retrieval/discovery or publication-wording gaps. Absence of evidence is not evidence of no announcement.','expected_results_date':str(expected) if expected else None,'date_status':'UNVERIFIED PLANNING ESTIMATE: prior-season SEC release +364 days; not a company announcement','prior_season_release':prior[0] if len(prior)==1 else prior,'conditional_opening_eastern':opening.isoformat() if opening else None,'conditional_opening_pacific':opening.astimezone(ZoneInfo('America/Los_Angeles')).isoformat() if opening else None,'earliest_actual_lock_date':None,'actual_lock_block':'Future verified publication evidence not accepted; estimated opening is conditional and is not an authorization. Need >=6 eligible observations and all live checks.','source_inventory':{'submissions':inv['submissions_manifest'],'companyfacts':inv['companyfacts_source']['manifest'],'source_gaps':inv['source_gaps']}})
    out.sort(key=lambda c:(c['tier'],-c['source_matched_quarters'],-c['verified_last_four_pairs'],c['expected_results_date'] or '9999',c['ticker']))
    for rank,c in enumerate(out,1):c['rank']=rank
    report={'prepared_at':datetime.now(timezone.utc).isoformat(),'financial_source_cutoff':'2026-11-20','universe_count':len(out),'tier_counts':dict(Counter(c['tier'] for c in out)),'six_or_more_source_matched':sum(c['source_matched_quarters']>=6 for c in out),'complete_four_announcement_pairs':sum(c['verified_last_four_pairs']==4 for c in out),'operationally_live_ready':0,'source_matched_total':sum(c['source_matched_quarters'] for c in out),'audited_quarter_total':sum(c['quarters_audited'] for c in out),'companies':out};save(REPORT.with_suffix('.json'),report);return report
if __name__=='__main__':
    d=build();print(json.dumps({k:v for k,v in d.items() if k!='companies'},indent=2))
