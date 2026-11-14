"""Reproduce the saved probe review without provider clients or accounting writes."""
import json,sqlite3
from pathlib import Path
from .prepare import ROOT,DATA,read,digest,write
from .validation import validate
from .runner import calendar_for
ATTEMPT='bb7bb97b-f98d-497c-847f-012086b915af'

def encoded(value):return len(json.dumps(value,sort_keys=True,separators=(',',':')).encode())

from .context import compact_document

def review():
    request=read(DATA/(ATTEMPT+'-request.json'));raw=read(DATA/(ATTEMPT+'-raw.json'))
    docs=request['payload']['documents'];model=json.loads(raw['text'])
    revalidation=validate(model,docs,calendar_for('A'))
    component=[]
    for doc in docs:
        component.append({'source_id':doc['source_id'],'document_json_bytes':encoded(doc),
            'canonical_characters':len(doc['canonical_text']),
            'canonical_json_bytes':encoded(doc['canonical_text']),'table_count':len(doc['tables']),
            'tables_json_bytes':encoded(doc['tables']),
            'table_text_value_bytes':sum(encoded(t['text']) for t in doc['tables']),
            'table_rows_value_bytes':sum(encoded(t['rows']) for t in doc['tables']),
            'table_surrounding_context_value_bytes':sum(encoded(t['surrounding_context']) for t in doc['tables'])})
    proposed={'documents':[compact_document(d) for d in docs]}
    original=encoded(request['payload']);smaller=encoded(proposed)
    conn=sqlite3.connect('file:'+str(DATA/'cost.sqlite3')+'?mode=ro',uri=True)
    try:
        accounting=[dict(zip(('id','reserved_nano','held_nano','accounted_nano','active'),r)) for r in conn.execute('SELECT id,reserved_nano,held_nano,accounted_nano,active FROM attempts')]
    finally:conn.close()
    assert len(accounting)==1 and accounting[0]['held_nano']==1120000000 and accounting[0]['accounted_nano'] is None
    original_names=[ATTEMPT+'-raw.json',ATTEMPT+'-result.json',ATTEMPT+'-request.json','pilot-0-input.json','run-20261113T203446771896Z.json','cost.sqlite3']
    return {'kind':'CACHED_RESPONSE_REVALIDATION_NOT_FRESH_MODEL_PERFORMANCE',
        'provider_calls':0,'original_artifacts':{n:digest((DATA/n).read_bytes()) for n in original_names},
        'saved_wire_body_available':False,'thinking_counter_origin':'SDK serialized null; original absent versus explicit null cannot be recovered',
        'original_usage':raw['usage'],'accounting_read_only':accounting,
        'original_input_tokens':89449,'provider_pre_count_tokens':89940,
        'token_attribution':'Provider saved only aggregate counters. Byte components below are exact JSON sizes, NOT per-component token counts. No inferred tokenizer attribution.',
        'components':component,'payload_json_bytes':original,
        'saved_system_prompt_utf8_bytes':len(request['system_prompt'].encode()),
        'saved_schema_json_bytes':encoded(request['response_schema']),
        'raw_html_in_inference_payload':False,'schema_counting_supplement_sent_to_generation':False,
        'proposed_full_text_compact_tables_json_bytes':smaller,'bytes_removed':original-smaller,
        'proposal_scope':'All text, all table cell values and header positions retained; duplicate representations removed. NOT activated for inference.',
        'revalidation':revalidation,'human_review_complete':False,'production_promotion':False}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior review; choose a new output path')
    write(a.output,review())
    print(a.output)
