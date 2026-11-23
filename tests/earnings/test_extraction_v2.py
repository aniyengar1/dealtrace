from decimal import Decimal as D
from copy import deepcopy
from earnings.extraction.v2.rules import extract,assign_status
from earnings.extraction.v2.pipeline import process

META=dict(company='GTLB',source_url='https://www.sec.gov/Archives/test-v2',accession='synthetic',exhibit='99.1',filed='2026-09-01',raw_sha256='synthetic')
def html(body,day='September 1, 2026'):
    return ('<p>NEW YORK – '+day+'</p>'+body).encode()


def test_arr_excluded_without_poisoning_revenue_history():
    body=html('<table><tr><th>Q3 FY2027 Guidance</th><th>FY2027 Guidance</th></tr><tr><td>Annual recurring revenue</td><td>$500 million to $510 million</td><td>$2 billion to $3 billion</td></tr><tr><td>Total revenue</td><td>$100 million to $110 million</td><td>$900 million to $950 million</td></tr></table>')
    prior={};text,cs,partials,abstain=process(body,META,prior)
    assert len(cs)==1 and D(cs[0]['low'])==100000000
    assert len(partials)==1 and D(partials[0]['low'])==900000000
    assert 'NON_CONSOLIDATED_METRIC' in {a['code'] for a in abstain}
    assert all(c['metric'] in ('consolidated_revenue','quarterly_consolidated_revenue') for c in prior.values())
    assert not any(D(c['low'])==500000000 for c in prior.values())
    assert text[cs[0]['quote_start']:cs[0]['quote_end']]==cs[0]['quote']
    assert 'Q3 FY2027' in cs[0]['context']['headers']


def test_implied_column_is_skipped_without_shifting_direct_columns():
    body=html('<table><tr><th>Q3 FY2027 Outlook</th><th>Implied Q4 FY2027 Outlook</th><th>FY2027 Outlook</th></tr><tr><td>Total revenue</td><td>$100 million to $110 million</td><td>$120 million to $130 million</td><td>$900 million to $950 million</td></tr></table>')
    _,obs,blocked=extract(body,META)
    assert {(c['metric'],c['start'],D(c['low'])) for c in obs}=={('quarterly_consolidated_revenue','2026-08-01',D(100000000)),('consolidated_revenue','2026-02-01',D(900000000))}
    assert any(b['code']=='IMPLIED_OR_DERIVED_TARGET' for b in blocked)


def test_explicit_annual_prose_never_inherits_quarterly_period():
    body=html('<p>For the third quarter of fiscal 2026, the Company expects net revenue to be in the range of $2.2 billion to $2.3 billion.</p><p>For 2026, the Company expects net revenue to be in the range of $10.3 billion to $10.5 billion.</p>')
    _,obs,_=extract(body,{**META,'company':'LULU'})
    assert {(c['metric'],D(c['low'])) for c in obs}=={('quarterly_consolidated_revenue',D(2200000000)),('consolidated_revenue',D(10300000000))}
    annual=next(c for c in obs if c['metric']=='consolidated_revenue')
    assert annual['start']=='2026-02-02' and annual['end']=='2027-01-31'


def test_status_requires_same_identity_and_direct_period():
    _,obs,_=extract(html('<p>For Q3 FY2027 the Company expects total revenue of $100 million to $110 million.</p>'),META)
    c=obs[0];key=(c['company'],c['metric'],c['start'],c['end']);old=deepcopy(c);old.update(low='90000000',high='95000000',filed='2026-08-01',status='initial')
    status,why=assign_status(c,{key:old},META);assert status=='raised'
    old['metric']='annual_recurring_revenue';assert assign_status(c,{key:old},META)[0] is None
    old['metric']=c['metric'];old['direct_guidance']=False;assert assign_status(c,{key:old},META)[0] is None


def test_unknown_annual_status_abstains_instead_of_becoming_initial():
    prior={};_,cs,partials,blocked=process(html('<p>For FY2027 the Company expects revenue of $900 million to $950 million.</p>'),META,prior)
    assert cs==[] and len(partials)==1 and partials[0]['status'] is None
    assert any(b['code']=='ANNUAL_STATUS_HISTORY_MISSING' for b in blocked)


def test_qualitative_high_end_requires_matching_earlier_range():
    body=html('<p>For the fourth quarter of fiscal 2025, the Company expects net revenue of $3.5 billion to $3.6 billion.</p>')
    meta={**META,'company':'LULU'};prior={};_,cs,_,_=process(body,meta,prior)
    assert cs
    new=html('<p>The Company now expects net revenue for the fourth quarter of fiscal 2025 to be toward the high end of its previously announced range.</p>','October 1, 2026')
    later={**meta,'filed':'2026-10-01','accession':'later'}
    _,cs,_,_=process(new,later,prior)
    assert len(cs)==1 and cs[0]['status']=='reaffirmed' and cs[0]['reference_input_id']
    _,cs,_,blocked=process(new,later,{})
    assert not cs and any(b['code']=='MISSING_REFERENCE' for b in blocked)


def test_ambiguous_multitarget_prose_does_not_emit_wrong_ranges():
    body=html('<p>For the full fiscal year 2027, the Company reaffirms guidance.</p><p>The Company expects first quarter total revenue of $100 million to $110 million, and full fiscal year total revenue of $900 million to $950 million.</p>')
    _,obs,blocked=extract(body,META)
    assert not obs and any(b['code']=='AMBIGUOUS_MULTI_TARGET_CLAUSE' for b in blocked)


def test_no_date_is_not_replaced_by_filing_date():
    _,obs,blocked=extract(b'<p>For Q3 FY2027 the Company expects revenue of $100 million to $110 million.</p>',META)
    assert not obs and any(b['code']=='UNRESOLVED_ISSUANCE_DATE' for b in blocked)


def test_repair_freeze_and_reserved_set_are_immutable_and_disjoint():
    import json,hashlib
    from pathlib import Path
    from datetime import datetime
    root=Path(__file__).resolve().parents[2]/'earnings/extraction/v2'
    frozen=json.loads((root/'rules_frozen_v2.json').read_text())
    for name,expected in frozen['files'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected
    assert hashlib.sha256((root/'reservation.json').read_bytes()).hexdigest()==frozen['reservation_sha256']
    gold=json.loads((root/'fresh_gold.json').read_text());old=json.loads((root.parent/'gold_v1.json').read_text())
    assert datetime.fromisoformat(frozen['frozen_at'])<datetime.fromisoformat(gold['curated_at'])
    assert hashlib.sha256((root/'fresh_gold.json').read_bytes()).hexdigest()==(root/'fresh_gold.sha256').read_text().strip()
    old_targets={(r['company'],r['metric'],r['start'],r['end']) for r in old['records']}
    assert not any((r['company'],r['metric'],r['start'],r['end']) in old_targets for r in gold['records'])
    old_accessions={r['accession'] for r in old['records']}
    assert not any(d['accession'] in old_accessions for d in gold['evaluation_documents']+gold['context_documents'])
    assert len(gold['records'])==20 and len(gold['evaluation_documents'])==10


def test_fresh_scores_count_abstentions_as_misses_not_invented_records():
    import json
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    result=json.loads((root/'earnings/validation/session4_repair_fresh_once.json').read_text())
    assert result['strict_record']['gold']==20 and result['strict_record']['predicted']==18
    assert result['strict_record']['true_positive']==18 and result['strict_record']['false_negative']==2
    assert D(result['strict_record']['precision'])==1 and D(result['strict_record']['recall'])==D('.9')
    assert result['abstention_counts']['ANNUAL_STATUS_HISTORY_MISSING']==2
    assert {e['company'] for e in result['errors']}=={'ADBE','LULU'}
    assert all(e['type']=='miss' for e in result['errors'])


def test_canonical_utf8_punctuation_survives_byte_input():
    from earnings.extraction.corpus import canonical
    assert canonical('<p>NEW YORK – September 1, 2026: $100–$110 million.</p>'.encode('utf-8')) == 'NEW YORK – September 1, 2026: $100–$110 million.'
