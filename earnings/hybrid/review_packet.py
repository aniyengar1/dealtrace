"""Reproducible owner review packet. Never marks actual human review complete."""
import hashlib
from datetime import datetime,timezone
from .prepare import ROOT,DATA,read,write
SEED='crosscheck-hybrid-owner-review-v1'
HIGH_RISK=['pilot-4','IOT-0001642896-24-000059','CRWD-0001535527-24-000017','pilot-19']

def selection(cases):
    rank=lambda c:hashlib.sha256((SEED+'|'+c['id']).encode()).hexdigest()
    random=sorted(cases,key=rank)[:4];ids={c['id'] for c in random}
    targeted=[next(c for c in cases if c['id']==i) for i in HIGH_RISK if i not in ids]
    return random,targeted

def run():
    cases=read(ROOT/'diagnostic_manifest.json')['cases'];random,targeted=selection(cases);chosen=random+targeted
    lines=['Crosscheck hybrid diagnostic — owner review packet','', '**No model inference has occurred. Human review is NOT complete.** These are existing source-curated/agent-reviewed examples; they have not been verified by the owner. Initial review can check reference labels; model interpretations/disputes will remain pending until authorized inference. Reviewing a sample does not verify every label or establish generalization.','',
    'Selection: four SHA256-ranked cases using seed `'+SEED+'`, plus up to four fixed prior-v2 high-risk cases not already sampled (segment actuals, implied guidance, ARR and acquisition scope). All related evidence for a release stays together. The targeted cases are known v2 diagnostic disputes, not newly observed hybrid errors. After inference, any additional hybrid disputes require a bounded packet revision; do not silently add work beyond two hours.','',
    f'Estimated workload: instructions10min + random{len(random)}×8min + additional high-risk{len(targeted)}×12min + summary10min = {20+len(random)*8+len(targeted)*12}min; reserve remaining time up to120min as buffer. Stop at two hours and leave remaining cases unreviewed. Estimates are planning assumptions, not a promise.','',
    'For each release: read the full relevant guidance, including negative metrics and targets omitted by an extractor. Verify total-company versus ARR/segment; reported versus adjusted/CC; amount and scale; annual versus quarterly boundaries; direct versus implied/historical; scope footnotes; and same-target revision evidence. Mark agree / correct / unresolved, record the supporting source and time spent. Exact quote membership does not prove the interpretation.','']
    entries=[]
    for case in chosen:
        origin='random' if case in random else 'targeted_prior_v2_risk';item=read(case['input_path']);doc=item['documents'][0];text=doc['canonical_text'];excerpt=case['review_excerpt'];a=text.find(excerpt[:70])
        if a<0:a=0
        context=text[max(0,a-600):min(len(text),a+3600)]
        full=DATA/(case['id']+'-source-review.md');full.write_text('Source: '+case['source_url']+'\n\n'+text+'\n\nTABLES\n\n'+'\n\n'.join(t['id']+'\n'+t['text'] for t in doc['tables'])+'\n')
        lines += [f"**{case['id']} — {case['company']} ({origin})**",'',f"[SEC source]({case['source_url']}) · accession `{case['accession']}` · filed {case['filed']}",f"[Complete pinned source text]({full})",'',f"Issues: {', '.join(case['tags'])}. Label provenance: {case['gold_kind']}.",'',context,'']
        gold=read(ROOT.parents[1]/case['gold_file'])['records']
        labels=[g for g in gold if g['id'] in case['gold_ids']]
        lines += ['Source-curated reference interpretations (agent labels; NOT owner verified):','','|Metric|Period|Low–high USD|Basis|Status|','|---|---|---:|---|---|']
        for g in labels:lines.append(f"|{g['metric']}|{g.get('start',g.get('fiscal_period',{}))}–{g.get('end','')}|{g.get('low')}–{g.get('high')}|{g.get('basis')}|{g.get('status')}|")
        lines.append('')
        if len(item['documents'])>1:
            prior=item['documents'][1];lines += [f"Prior status context: [SEC source]({prior['source_url']}) filed {prior['filed']}. Compare the same revenue target; do not borrow another metric’s revision.",'']
        lines += ['Model interpretation: **PENDING AUTHORIZED INFERENCE**.','Owner decision: **NOT PROVIDED**. Corrections / exact evidence / minutes spent: __________.','']
        entries.append({'case_id':case['id'],'selection':origin,'source_url':case['source_url'],'input_sha256':case['input_sha256'],'source_curation':case['gold_kind'],'agent_review':'prior diagnostic source review, not actual owner review','model_review':'not_run','human_review_status':'not_started','human_reviewer':None,'human_reviewed_at':None,'human_minutes':None,'human_decision':None})
    (ROOT/'owner_review_packet.md').write_text('\n'.join(lines).rstrip()+'\n')
    write(ROOT/'owner_review_manifest.json',{'created_at':datetime.now(timezone.utc).isoformat(),'seed':SEED,'algorithm':'four minimum SHA256(seed|case_id) then fixed high-risk union','random_cases':[x['id'] for x in random],'targeted_cases':[x['id'] for x in targeted],'estimated_minutes':20+len(random)*8+len(targeted)*12,'hard_owner_workload_minutes':120,'human_review_complete':False,'cases':entries})
    print('Prepared',len(entries),'review cases;',20+len(random)*8+len(targeted)*12,'estimated minutes; human review pending')

if __name__=='__main__':run()
