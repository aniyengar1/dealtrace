from copy import deepcopy
from pathlib import Path
from hashlib import sha256
from decimal import Decimal as D
import json
import pytest
from earnings.extraction.corpus import canonical,gold,ROOT
from earnings.extraction.rules import extract,references,period

META=dict(company='GTLB',source_url='https://www.sec.gov/Archives/test',accession='test-accession',exhibit='99.1',filed='2026-09-01',raw_sha256='test')

def get(body,metadata=None):
    text=canonical(('<p>September 1, 2026</p>'+body).encode())
    return text,extract(text,metadata or META)


def test_dual_columns_and_literal_unicode_offsets():
    text,(cs,_) = get('<h2>Outlook</h2><table><tr><th>Q3 FY 2027 Guidance</th><th>FY 2027 Guidance (in millions)</th></tr><tr><td>Revenue</td><td>$281 – $283</td><td>$1,129 – $1,133</td></tr></table>')
    assert len(cs)==2
    assert {(c['metric'],D(c['low']),D(c['high'])) for c in cs}=={('quarterly_consolidated_revenue',D(281000000),D(283000000)),('consolidated_revenue',D(1129000000),D(1133000000))}
    for c in cs:assert text[c['quote_start']:c['quote_end']]==c['quote'] and c['review_required']
    assert cs[0]['start']=='2026-08-01' and cs[0]['end']=='2026-10-31'


def test_narrative_and_mixed_scales_no_floats():
    _,(cs,_)=get('For the full year fiscal 2027 the Company expects total revenue of $900 million to $1.1 billion.')
    assert len(cs)==1 and D(cs[0]['low'])==D(900000000) and D(cs[0]['high'])==D(1100000000)
    _,(cs,_)=get('For the third quarter fiscal 2027, revenues are expected to be in the range of: $281 million to $283 million.')
    assert len(cs)==1 and D(cs[0]['low'])==D(281000000)


@pytest.mark.parametrize('phrase',[
    'Subscription revenue of $100 million to $110 million',
    'Segment revenue of $100 million to $110 million',
    'Total revenue growth of 10% to 12%',
    'ARR of $100 million to $110 million',
    'Adjusted revenue of $100 million to $110 million',
    'Organic revenue of $100 million to $110 million',
    'Constant-currency revenue of $100 million to $110 million',
])
def test_reject_ineligible_metrics(phrase):
    _,(cs,_)=get('Q3 FY2027 Guidance: '+phrase)
    assert cs==[]


def test_reported_actuals_are_not_targets_even_after_guidance_headline():
    _,(cs,_)=get('Raises FY2027 guidance. Third Quarter Fiscal Year 2027 Financial Highlights: Adobe achieved record revenue of $6.76 billion.')
    assert cs==[]


def test_invalid_ranges_and_missing_units_or_fiscal_label_block():
    _,(cs,rejected)=get('Q3 FY2027 Guidance: Revenue $110 million to $100 million')
    assert cs==[] and rejected[0]['code']=='INVALID_RANGE'
    _,(cs,rejected)=get('Q3 FY2027 Guidance: Revenue $100 to $110')
    assert cs==[] and rejected[0]['code']=='UNRESOLVED_UNIT'
    _,(cs,rejected)=get('Guidance: Revenue $100 million to $110 million')
    assert cs==[] and rejected[0]['code']=='UNRESOLVED_FISCAL_LABEL'


def test_point_guidance_not_missing_high():
    _,(cs,_)=get('Q3 FY2027 Guidance: Revenue $209.5 million')
    assert len(cs)==1 and cs[0]['low']==cs[0]['high']


def test_same_amounts_different_decimal_spellings_deduplicate():
    _,(cs,_)=get('Q3 FY2027 Guidance: Revenue $281 million to $283 million. Q3 FY2027 Guidance: Revenue $281.0 million to $283.0 million.')
    assert len(cs)==1


def test_reaffirmation_requires_prior_extracted_version_and_preserves_link():
    _,(cs,_)=get('Q3 FY2027 Guidance: Revenue $281 million to $283 million.')
    old=cs[0];key=('GTLB',old['metric'],old['start'],old['end'])
    meta={**META,'filed':'2026-10-01','accession':'new'};text='October 1, 2026. Company reaffirms Q3 FY2027 guidance.'
    assert references(text,meta,{})==[]
    result=references(text,meta,{key:old})
    assert len(result)==1 and result[0]['status']=='reaffirmed' and result[0]['carried_from_candidate_id']==old['id']
    assert result[0]['low']==old['low'] and result[0]['source_url']==meta['source_url']
    assert text[result[0]['quote_start']:result[0]['quote_end']]==result[0]['quote']
    future=deepcopy(old);future['filed']='2026-11-01'
    assert references(text,meta,{key:future})==[]


def test_week_calendars_preserve_53_week_q4_and_issuer_year_labels():
    a,b=period('LULU',2024,4)
    from datetime import date
    assert (a,b)==('2024-10-28','2025-02-02') and (date.fromisoformat(b)-date.fromisoformat(a)).days+1==98
    assert period('IOT',2025,4)==('2024-11-03','2025-02-01')
    assert period('ADBE',2026,4)==('2026-08-29','2026-11-27')


def test_gold_checksum_source_files_and_group_split_frozen():
    data=gold();groups={}
    for r in data['records']:groups.setdefault((r['company'],r['accession']),set()).add(r['split'])
    assert len(data['records'])==134 and all(len(v)==1 for v in groups.values())
    assert {r['company'] for r in data['records'] if r['split']=='heldout'}=={'CRWD','IOT','LULU'}
    root=ROOT.parents[1]
    for path,expected in data['source_file_sha256'].items():assert sha256((root/path).read_bytes()).hexdigest()==expected


def test_frozen_rule_files_match_pre_heldout_hashes():
    frozen=json.loads((ROOT/'rules_frozen_v1.json').read_text())
    for name,expected in frozen['files'].items():assert sha256((ROOT/name).read_bytes()).hexdigest()==expected


@pytest.mark.xfail(strict=True,reason='Known held-out failure: frozen v1 accepts annual recurring revenue as total revenue; do not tune and relabel this holdout')
def test_known_gap_annual_recurring_revenue_must_not_be_consolidated_target():
    _,(cs,_)=get('Q3 FY2027 Guidance: Annual recurring revenue $500 million to $510 million.')
    assert cs==[]


@pytest.mark.xfail(strict=True,reason='Known held-out failure: frozen v1 confuses implied-quarter headings with directly issued quarterly targets')
def test_known_gap_implied_quarter_is_not_direct_guidance():
    _,(cs,_)=get('Q3 FY2027 Outlook Implied Q4 FY2027 Outlook Total revenue $398 million to $400 million.')
    assert not cs or all(c['start']=='2026-08-01' for c in cs)
