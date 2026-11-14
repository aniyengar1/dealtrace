"""Consumed diagnostic comparison and bounded owner packet, never promotion."""
import argparse,json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from datetime import datetime,timezone
from .prepare import ROOT,DATA,read,write
from .review_packet import selection
from earnings.extraction.v2.evaluate import score

def disposition(record):
    if record['deterministic_errors']:return 'rejected'
    if record['review_flags'] or record['review_status']!='human_review_approved':return 'flagged'
    raise ValueError('No human-approved acceptance is authorized for this diagnostic')

def analyze(run):
    if run.get('stage')!='diagnostic_only':raise ValueError('Diagnostic run required')
    manifest=read(ROOT/'diagnostic_manifest.json');by={r['case_id']:r for r in run['results']};cases=[]
    for case in manifest['cases']:
        item=by.get(case['id'],{});result=item.get('result',{});validation=result.get('validation',{})
        gold=[g for g in read(ROOT.parents[1]/case['gold_file'])['records'] if g['id'] in case['gold_ids']]
        records=[];proposals=[];counts=Counter();errors=Counter()
        for record in validation.get('observations',[]):
            o=record['proposal']
            if o['source_id']!='current':counts['prior_context_observations']+=1;continue
            category=disposition(record)
            counts[category]+=1;errors.update(record['deterministic_errors'])
            records.append({'id':record['id'],'category':category,'proposal':o,'resolved_status':record['resolved_status'],
                'low':record['normalized_low'],'high':record['normalized_high'],'start':record['resolved_period_start'],'end':record['resolved_period_end'],
                'errors':record['deterministic_errors'],'review_flags':record['review_flags'],'evidence_locations':record['evidence_locations']})
            if o['metric_class'] not in ('consolidated_revenue','net_sales') or o['scope']!='consolidated' or o['guidance_type']!='direct' or o['basis_kind']!='reported' or o['currency']!='USD':counts['noneligible_current_observations']+=1;continue
            proposals.append({'id':record['id'],'company':case['company'],'source_url':case['source_url'],
                'metric':'quarterly_consolidated_revenue' if o['fiscal_quarter'] else 'consolidated_revenue',
                'start':record['resolved_period_start'],'end':record['resolved_period_end'],'low':record['normalized_low'],'high':record['normalized_high'],
                'unit':o['currency'],'basis':'US_GAAP_consolidated_reported' if o['basis_kind']=='reported' and not o['scope_qualifiers'] else 'REVIEW_REQUIRED:'+o['basis_kind']+':'+','.join(o['scope_qualifiers']),
                'status':record['resolved_status'],'issued':{'start':o['issued_start'],'end':o['issued_end'],'precision':o['issued_precision']},
                'quote':' '.join(e['quote'] for e in o['evidence'])})
        whole=case['gold_file'].endswith('pilot_s5/gold.json')
        agreement=score(gold,proposals,whole)
        range_matches=[]
        for g in gold:
            matches=[r['id'] for r in records if r['proposal']['metric_class'] in ('consolidated_revenue','net_sales') and r['proposal']['guidance_type']=='direct' and r['proposal']['basis_kind']=='reported' and r['end']==g['end'] and r['proposal']['currency']==g['unit'] and r['low'] is not None and r['high'] is not None and Decimal(r['low'])==Decimal(g['low']) and Decimal(r['high'])==Decimal(g['high'])]
            range_matches.append({'gold_id':g['id'],'proposal_ids':matches,'criterion':'metric/end/currency/Decimal range only; NOT source, full-period, status, basis-review or acceptance validation'})
        cases.append({'reference_range_identification_NOT_ACCEPTANCE':range_matches,'reference_ranges_not_proposed':sum(not r['proposal_ids'] for r in range_matches),'case_id':case['id'],'company':case['company'],'source_url':case['source_url'],'source_filed':case['filed'],
            'case_state':item.get('status',result.get('status','not_run')),'gold_scope':'whole_release_agent_curated' if whole else 'old_positive_only_metric_scope',
            'gold_targets':len(gold),'counts':dict(counts),'errors':dict(errors),'records':records,
            'gold_ids':[g['id'] for g in gold],'gold_not_accepted':len(gold),
            'proposal_field_agreement_NOT_ACCEPTED_NOT_HUMAN_REVIEWED':agreement,
            'structured_output_status':validation.get('status','parsed' if 'observations' in validation else 'no_output'),
            'model_version':result.get('returned_model_version'),'attempt_id':result.get('attempt_id'),'finish_reasons':result.get('finish_reasons')})
    totals=Counter()
    for c in cases:totals.update(c['counts'])
    return {'kind':'CONSUMED_DIAGNOSTIC_NOT_FRESH_NOT_HUMAN_VALIDATED','recorded_at':datetime.now(timezone.utc).isoformat(),
        'stopped_reason':run.get('stopped_reason'),'run_started_at':run['started_at'],'run_finished_at':run['finished_at'],
        'case_count':len(cases),'counts':dict(totals),'gold_targets':sum(c['gold_targets'] for c in cases),
        'reference_ranges_not_proposed':sum(c['reference_ranges_not_proposed'] for c in cases),'gold_not_accepted':sum(c['gold_not_accepted'] for c in cases),'cases':cases,'cost_ledger':run['cost_ledger'],
        'human_review_complete':False,'fresh_inference_performed':False,
        'limitations':'No flagged/rejected proposal counts as accepted or correct. Field agreement against consumed source-curated labels is diagnostic only, not acceptance, independent review or generalization. Old positive-only scopes leave additional targets unjudged.'}

def packet(analysis):
    manifest=read(ROOT/'diagnostic_manifest.json')['cases'];random,targeted=selection(manifest);chosen=random+targeted
    supplement=[c for c in manifest if c['id'] not in {x['id'] for x in chosen}];chosen+=supplement
    by={c['case_id']:c for c in analysis['cases']};entries=[]
    lines=['# Owner review packet — revised ten-release diagnostic','',
        '**Human review pending.** Only the owner supplies human decisions. Source-curated labels, model proposals, deterministic checks and owner adjudication are separate. No sample review validates every label.','',
        'Original four seeded random cases and three fixed prior-risk cases are unchanged. Three remaining releases are supplemental diagnostic/disputed coverage; no unfavorable case was removed or replaced. Whole release groups stay together.','',
        'Budget: instructions8min + random4×7min + high-risk3×10min + supplemental3×5min + summary7min = **88min**. Estimates are planning assumptions; use up to32min buffer and stop at **120min**, leaving unfinished cases explicitly unreviewed.','',
        'Read complete relevant outlook sections, headers and footnotes using the full pinned text/SEC links, including targets missed or abstained on. Verify metric, scope, period, basis, units, direct/implied status and issuance/revision evidence. Exact quotes and passed code checks do not establish semantic truth. Record agree/correct/unresolved and time spent; no trading recommendations.','']
    for c in chosen:
        row=by[c['id']];origin='preselected_random' if c in random else 'preselected_high_risk' if c in targeted else 'supplemental_diagnostic'
        minutes=7 if c in random else 10 if c in targeted else 5
        full=DATA/(c['id']+'-source-review.md')
        lines += [f"## {c['company']} — {c['id']} ({origin}, {minutes}min)",'',f"[Official SEC source]({c['source_url']}) · filed {c['filed']} · accession `{c['accession']}`",f"[Full pinned release and tables]({full})",'',f"Source curation: {c['gold_kind']}; actual owner review: **NOT PROVIDED**. Model run: {row['case_state']}; structured output: {row['structured_output_status']}.",'',
            'Relevant source-curated guidance content (not model evidence):','',c['review_excerpt'],'','Model proposals below are untrusted; location results do not approve semantics.','']
        for r in row['records']:
            o=r['proposal'];lines += [f"- `{r['id']}` **{r['category']}**: {o['metric_label']}, FY{o['fiscal_year']} Q{o['fiscal_quarter'] or 'annual'}, USD {r['low']}–{r['high']}; claimed status {o['status']}, resolved {r['resolved_status']}. Errors: {', '.join(r['errors']) or 'none'}. Review: {', '.join(r['review_flags'])}."]
            for e in r['evidence_locations']:
                lines += [f"  Evidence proposal ({'/'.join(e['roles'])}), {e['status']}: {e['original']['quote']}"]
        gold=[g for g in read(ROOT.parents[1]/c['gold_file'])['records'] if g['id'] in c['gold_ids']]
        lines+=['','Source-curated reference targets (not owner adjudication):','']
        for g in gold:lines.append(f"- `{g['id']}` {g['metric']}, {g['start']}–{g['end']}, USD {g['low']}–{g['high']}, status {g['status']}.")
        lines+=['','Decision required: identify all actual targets (including omitted ones); resolve or retain each flagged metric/period/status; provide source evidence for corrections. Owner decision / evidence / minutes: **NOT PROVIDED**.','']
        entries.append({'case_id':c['id'],'selection':origin,'estimated_minutes':minutes,'source_curation':c['gold_kind'],'model_output':'quarantined','deterministic_counts':row['counts'],'human_review_status':'pending','human_decision':None,'human_reviewer':None,'human_reviewed_at':None,'human_minutes':None})
    (ROOT/'owner_review_packet_v4.md').write_text('\n'.join(line.rstrip() for line in '\n'.join(lines).splitlines()).rstrip()+'\n')
    write(ROOT/'owner_review_manifest_v4.json',{'created_at':datetime.now(timezone.utc).isoformat(),'selection_seed':read(ROOT/'owner_review_manifest.json')['seed'],
        'original_random_cases':[c['id'] for c in random],'original_high_risk_cases':[c['id'] for c in targeted],
        'supplemental_cases':[c['id'] for c in supplement],'cases_removed_or_replaced':[],
        'estimated_minutes':88,'hard_minutes':120,'human_review_complete':False,'cases':entries})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if DATA.resolve() not in a.run.resolve().parents:raise ValueError('Own diagnostic cache only')
    if a.output.exists():raise ValueError('Preserve prior analysis')
    result=analyze(read(a.run));write(a.output,result);packet(result);print(json.dumps({'counts':result['counts'],'gold_targets':result['gold_targets'],'accepted':0}))
