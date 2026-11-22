"""Consumed diagnostic score only. Never fresh evaluation or live scoring."""
import argparse,json
from pathlib import Path
from .prepare import ROOT,DATA,read,write
from earnings.extraction.v2.evaluate import score

def evaluate(run_path,output):
    path=Path(run_path).resolve()
    if DATA.resolve() not in path.parents:raise ValueError('Only own diagnostic run files permitted')
    run=read(path)
    if run.get('stage')!='diagnostic_only':raise ValueError('Fresh inference/evaluation forbidden in this stage')
    cases={c['id']:c for c in read(ROOT/'diagnostic_manifest.json')['cases']};whole_expected=[];whole_candidates=[];old_expected=[];old_candidates=[];not_run=[];abstentions=[]
    for cid,case in cases.items():
        item=next((r for r in run.get('results',[]) if r.get('case_id')==cid and r.get('result',{}).get('status')=='response'),None)
        if not item:not_run.append(cid);continue # Not-run is NOT a model miss/abstention.
        gold=read(ROOT.parents[1]/case['gold_file'])['records'];expected=[g for g in gold if g['id'] in case['gold_ids']]
        candidates=[]
        for record in item['result'].get('validation',{}).get('observations',[]):
            o=record['proposal']
            if o['source_id']!='current':continue
            if record['deterministic_errors']:
                abstentions.append({'case_id':cid,'candidate_id':record['id'],'codes':record['deterministic_errors']});continue
            candidates.append({'id':record['id'],'company':case['company'],'source_url':case['source_url'],'accession':case['accession'],'filed':case['filed'],'exhibit':'99.1','metric':'quarterly_consolidated_revenue' if o['fiscal_quarter'] else 'consolidated_revenue','start':record['resolved_period_start'],'end':record['resolved_period_end'],'low':record['normalized_low'],'high':record['normalized_high'],'unit':o['currency'],'basis':'US_GAAP_consolidated_reported' if not o['scope_qualifiers'] else 'SCOPE_QUALIFIERS_REQUIRE_REVIEW:'+','.join(o['scope_qualifiers']),'status':o['status'],'issued':{'start':o['issued_start'],'end':o['issued_end'],'precision':o['issued_precision']}})
        if case['gold_file'].endswith('pilot_s5/gold.json'):whole_expected+=expected;whole_candidates+=candidates
        else:old_expected+=expected;old_candidates+=candidates
    result={'kind':'consumed_diagnostic_NOT_fresh_NOT_human_validated','performance_status':'NOT_EVALUATED_NO_MODEL_RESULTS' if len(not_run)==len(cases) else 'DIAGNOSTIC_ONLY','not_run_cases':not_run,'abstentions':abstentions,'whole_release_pilot_scope':score(whole_expected,whole_candidates,True) if whole_expected else None,'old_positive_only_scope':score(old_expected,old_candidates,False) if old_expected else None,'limitations':'Old positive-only scope leaves other document/metric cells unjudged. Scope qualifiers require review, never silently mapped to generic GAAP. Deterministic-pass proposals remain quarantined and do not establish semantic correctness. No human-reviewed precision claim.'}
    with Path(output).open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run');p.add_argument('--output',required=True);a=p.parse_args();print(evaluate(a.run,a.output)['performance_status'])
