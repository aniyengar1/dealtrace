"""Local cache preparation only; no model, SDK client or fresh body access."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
from bs4 import BeautifulSoup
from earnings.sec import CACHE
from earnings.extraction.corpus import canonical
from earnings.models import dumps
ROOT=Path(__file__).parent
DATA=CACHE/'hybrid_diagnostic_vertex_v1'
PILOT_INDEXES={0:['annual_vs_quarterly'],1:['center_plus_tolerance'],4:['segment_actual_false_positive','table_columns'],11:['period_ending_table','missed_target'],14:['net_sales'],19:['acquisition_scope'],27:['metric_specific_revision_status'],28:['reported_vs_constant_currency','between_and_range']}

def read(p):return json.loads(Path(p).read_text())
def write(p,data):Path(p).write_text(dumps(data)+'\n')
def digest(b):return hashlib.sha256(b).hexdigest()

def cached_source(url):
    # URL manifest lookup only. No network fallback; fresh bodies never opened.
    m=read(CACHE/(digest(url.encode())+'.json'));b=(CACHE/m['body']).read_bytes()
    if m['url']!=url or digest(b)!=m['sha256']:raise ValueError('Pinned cache mismatch')
    return b,m

def source(url,company,filed,accession,kind,source_id):
    fresh=read(ROOT/'fresh_manifest.json')
    for issuer in fresh['issuers']:
        if issuer['company']==company:raise ValueError('Fresh issuer embargo')
    body,m=cached_source(url);text=canonical(body);soup=BeautifulSoup(body,'html.parser');tables=[]
    for table in soup.find_all('table'):
        # Only leaves preserve actual cells without dumping duplicate wrappers.
        if table.find('table'):continue
        txt=canonical(str(table).encode());a=text.find(txt)
        if a<0:continue
        rows=[[{'text':canonical(str(cell).encode()),'tag':cell.name,'rowspan':cell.get('rowspan','1'),'colspan':cell.get('colspan','1')} for cell in row.find_all(['th','td'],recursive=False)] for row in table.find_all('tr')]
        tables.append({'id':f'{source_id}:table:{len(tables)}','start':a,'end':a+len(txt),'text':txt,'rows':rows,'surrounding_context':text[max(0,a-600):a]})
    return {'source_id':source_id,'company':company,'source_url':url,'filed':filed,'accession':accession,'kind':kind,'source_sha256':m['sha256'],'canonical_sha256':digest(text.encode()),'canonical_text':text,'tables':tables},m

def prepare():
    DATA.mkdir(parents=True,exist_ok=True)
    if not (ROOT/'fresh_manifest.json').exists():raise ValueError('Reserve and commit fresh manifest before preparation')
    pilot=read(ROOT.parent/'pilot_s5/gold.json');sample=read(ROOT.parent/'pilot_s5/sample.json')['groups'];old=read(ROOT.parent/'extraction/gold_v1.json')['records'];cases=[]
    for index,tags in PILOT_INDEXES.items():
        g=sample[index];src=g['source'];labels=[x for x in pilot['records'] if x['sample_index']==index];review=next(r for r in pilot['release_reviews'] if r['sample_index']==index)
        cases.append({'id':'pilot-'+str(index),'company':g['company'],'tags':tags,'source_url':g['guidance_source_url'],'filed':src['filed'],'accession':src['accession'],'gold_ids':[x['id'] for x in labels],'gold_kind':'source_curated_agent_reviewed_whole_release_not_human_verified','gold_file':'earnings/pilot_s5/gold.json','context':review.get('prior_status_evidence'),'review_excerpt':review['guidance_quote']})
    for company,acc,tags in [('IOT','0001642896-24-000059',['direct_vs_implied','ARR_vs_revenue','table_columns']),('CRWD','0001535527-24-000017',['ARR_vs_revenue','revision_status_ambiguity'])]:
        labels=[x for x in old if x['company']==company and x['accession']==acc];g=labels[0]
        cases.append({'id':company+'-'+acc,'company':company,'tags':tags,'source_url':g['source_url'],'filed':g['filed'],'accession':acc,'gold_ids':[x['id'] for x in labels],'gold_kind':'existing_positive_only_source_curated_agent_reviewed_not_human_verified','gold_file':'earnings/extraction/gold_v1.json','context':None,'review_excerpt':g['quote'],'gold_limitations':'Old positive-only scope not exhaustive annual/quarterly negatives; human review must include missed/implied/ARR content. No open-world precision claim from these labels.'})
    inventory=[]
    for case in cases:
        doc,m=source(case['source_url'],case['company'],case['filed'],case['accession'],'current','current');docs=[doc];manifests=[m]
        if case['context']:
            c=case['context'];d,cm=source(c['source_url'],case['company'],c['filed'],c['accession'],'prior_context','prior');docs.append(d);manifests.append(cm)
        item={'case':case,'documents':docs,'source_manifests':manifests,'preprocessing':'whole canonical release plus complete leaf-table cells/headers/context, independent of v2 hits; no content truncation'}
        path=DATA/(case['id']+'-input.json');write(path,item)
        inventory.append({**case,'input_path':str(path),'input_sha256':digest(path.read_bytes()),'source_manifests':manifests,'status':'READY_LOCAL_ONLY','model_result':'NOT_RUN','human_review':'PENDING_OWNER_REVIEW'})
    output={'prepared_at':datetime.now(timezone.utc).isoformat(),'stage':'diagnostic_local_preparation_no_inference','fresh_manifest_sha256':digest((ROOT/'fresh_manifest.json').read_bytes()),'cases':inventory,'human_reviewer':'Owner only; not yet reviewed','source_curator':'Prior Codex source-curated labels','agent_review':'Previous diagnostic review; not human verification'}
    target=ROOT/'diagnostic_manifest.json'
    if target.exists():
        previous=read(target)
        if previous['cases']!=output['cases']:raise ValueError('Manifest drift; preserve prior evidence and version explicitly')
    else:write(target,output)
    return output

if __name__=='__main__':
    result=prepare();print(dumps({'cases':len(result['cases']),'inference_performed':False,'fresh_bodies_opened':False}))
