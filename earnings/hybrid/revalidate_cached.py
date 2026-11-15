"""Post-diagnostic validator repair, from pinned existing responses only.

No inference, CountTokens, fresh release reads, production writes or ledger writes.
Original raw responses, validations and review packets remain unchanged.
"""
import argparse,json,sqlite3
from copy import deepcopy
from collections import Counter
from pathlib import Path
from datetime import datetime,timezone
from .prepare import ROOT,DATA,read,digest,write
from .runner import calendar_for
from .validation import validate
from .batch_review import analyze
from .ledger import CEILING,usd,known_subtotal

RUN=DATA/'run-20261114T032437489379Z.json'

def accounting():
    with sqlite3.connect('file:'+str(DATA/'cost.sqlite3')+'?mode=ro',uri=True) as c:
        c.row_factory=sqlite3.Row
        rows=[dict(r) for r in c.execute('SELECT * FROM attempts ORDER BY created_at,id')]
        events=[dict(r) for r in c.execute('SELECT * FROM events ORDER BY id')]
        held=sum(r['held_nano'] for r in rows)
        return {'read_only':True,'attempts':len(rows),'active_attempts':sum(r['active'] for r in rows),
            'ceiling_usd':usd(CEILING),'known_accounted_usd':usd(sum(r['accounted_nano'] or 0 for r in rows)),
            'outstanding_reservations_usd':usd(sum(r['held_nano'] for r in rows if r['accounted_nano'] is None)),
            'occupancy_usd':usd(held),'headroom_usd':usd(CEILING-held),
            'original_probe_reservation_usd':usd(next(r['held_nano'] for r in rows if r['id']=='bb7bb97b-f98d-497c-847f-012086b915af')),
            'known_subtotals_usd_NOT_ADDITIONAL_CHARGES':usd(sum(known_subtotal({'prompt_token_count':r['input_tokens'],'candidates_token_count':r['candidate_tokens'],'thoughts_token_count':r['thinking_tokens']}) or 0 for r in rows)),
            'attempt_rows_sha256':digest(json.dumps(rows,sort_keys=True).encode()),'event_rows_sha256':digest(json.dumps(events,sort_keys=True).encode()),
            'provider_billing_cap_guaranteed':False}

def review():
    original=read(RUN);manifest=read(ROOT/'diagnostic_manifest.json');new=deepcopy(original);changes=[]
    paths=[RUN,DATA/'cost.sqlite3',ROOT/'fresh_manifest.json',ROOT/'owner_review_packet_v4.md',ROOT/'owner_review_manifest_v4.json',ROOT.parent/'validation/hybrid_v4_diagnostic_final_analysis.json']
    for suffix in ('-raw.json','-request.json','-result.json'):paths.extend(DATA.glob('*'+suffix))
    hashes={str(p):digest(p.read_bytes()) for p in paths};before=accounting()
    for case in manifest['cases']:
        inputpath=Path(case['input_path']);body=inputpath.read_bytes()
        if digest(body)!=case['input_sha256']:raise ValueError('Pinned original diagnostic input changed')
        saved=next(r for r in new['results'] if r['case_id']==case['id'])['result'];old=saved['validation']
        revised=validate(json.loads(saved['text']),json.loads(body)['documents'],calendar_for(case['company']))
        saved['validation']=revised
        for a,b in zip(old['observations'],revised['observations']):
            removed=sorted(set(a['deterministic_errors'])-set(b['deterministic_errors']));added=sorted(set(b['deterministic_errors'])-set(a['deterministic_errors']))
            if removed or added:
                changes.append({'case_id':case['id'],'company':case['company'],'source_id':b['proposal']['source_id'],'original_id':a['id'],'repair_id':b['id'],
                    'removed_errors':removed,'added_errors':added,'remaining_errors':b['deterministic_errors'],
                    'original_period':[a['resolved_period_start'],a['resolved_period_end']],'repaired_period':[b['resolved_period_start'],b['resolved_period_end']],
                    'claimed_status':b['proposal']['status'],'resolved_status':b['resolved_status'],'range_evidence_checks_passed':b['range_evidence_checks_passed']})
    result=analyze(new);result.update(kind='POST_DIAGNOSTIC_VALIDATOR_REPAIR_NOT_FRESH_PERFORMANCE',validation_version='post-diagnostic-validator-repair-v1',
        original_run=str(RUN),original_artifacts_sha256=hashes,changes=changes,accepted=0,provider_calls=0,token_count_calls=0,
        current_accounting=before,original_run_cost_snapshot_is_historical=True)
    after=accounting()
    assert before==after and hashes=={str(p):digest(p.read_bytes()) for p in paths}
    result['originals_and_ledger_unchanged']=True
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Never overwrite an evaluation artifact')
    r=review();write(a.output,r)
    print(json.dumps({'counts':r['counts'],'accepted':r['accepted'],'changed_records':len(r['changes']),'accounting':r['current_accounting']}))
