"""Research artifacts remain outside production and respect source-period gates."""
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from earnings.research.scaling_2027q1_packets import actual_candidates, source_issue
from earnings.research.scaling_2027q1_report import classify

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / 'earnings/reports/scaling_lock_readiness_2027Q1.json'


def test_all_64_have_eight_audited_quarters_and_counts_reconcile():
    d = json.loads(REPORT.read_text())
    screen = json.loads((ROOT / 'earnings/reports/scaling_universe_2027Q1.json').read_text())
    expected = {c['ticker'] for c in screen['companies'] if c['readiness_tier'] == 'R1'}
    assert {c['ticker'] for c in d['companies']} == expected
    assert len(expected) == 64
    assert d['audited_quarter_total'] == 512
    assert sum(c['source_matched_quarters'] for c in d['companies']) == d['source_matched_total']
    for c in d['companies']:
        assert len(c['quarter_rows']) == 8
        assert len({r['result_release']['report_date'] for r in c['quarter_rows']}) == 8
        assert c['source_matched_quarters'] == sum(not r['blocks'] for r in c['quarter_rows'])
        assert c['earliest_actual_lock_date'] is None
        assert c['date_status'].startswith('UNVERIFIED')


def test_every_source_matched_pair_has_dates_versions_and_exact_inputs():
    for c in json.loads(REPORT.read_text())['companies']:
        for r in c['quarter_rows']:
            if r['blocks']:
                assert r['outcome'] is None
                continue
            g, a = r['guidance'], r['actual']
            assert g['issued'] <= r['historical_guidance_cutoff']
            assert g['filed'] <= r['historical_guidance_cutoff']
            assert a['filed'] <= '2026-11-20'
            assert a['start'] <= a['end'] < r['result_release']['report_date']
            assert a['research_fact_id'] and g['research_version_id']
            assert g['url'].startswith('https://www.sec.gov/Archives/')
            assert r['actual_source']['url'].startswith('https://www.sec.gov/Archives/')
            assert len(g['sha256']) == len(r['actual_source']['sha256']) == 64
            assert r['outcome'] == classify(Decimal(a['value']), Decimal(g['low']), Decimal(g['high']))
            assert r['reconciliation']['kind']


def test_no_partial_announcement_study_is_called_typical():
    for c in json.loads(REPORT.read_text())['companies']:
        matches = {x['scheduled_release'] for x in c['announcement_pairs'] if x['in_last_four']}
        assert matches <= set(c['last_four_results_dates'])
        if len(matches) != 4:
            assert c['typical_last_four_gap'] is None
        for x in c['announcement_pairs']:
            assert x['observed_at']
            assert x['lead_days'] == (date.fromisoformat(x['scheduled_release']) - date.fromisoformat(x['issued'])).days


def test_period_and_scope_exclusions_not_replaced_with_easier_quarters():
    cs = {c['ticker']:c for c in json.loads(REPORT.read_text())['companies']}
    assert cs['RMBS']['source_matched_quarters'] < 6
    assert 'COMPONENTS_ONLY' in cs['RMBS']['quarter_rows'][1]['blocks'][0]
    assert 'SEGMENT_GUIDANCE' in cs['APP']['quarter_rows'][5]['blocks'][0]
    assert any('PERIOD_MISMATCH' in x for x in cs['FORM']['quarter_rows'][2]['blocks'])
    for t, i in [('DOCS', 2), ('ONTO', 4), ('DOCN', 6)]:
        assert any('EARLIER_COMPLETED_PERIOD' in x for x in cs[t]['quarter_rows'][i]['blocks'])
    for r in cs['PCTY']['quarter_rows']:
        assert r['actual']['concept'] == 'Revenues'


def fact(start, end, value, filed, accession='original'):
    return {'start':start, 'end':end, 'val':value, 'filed':filed, 'form':'10-Q', 'accn':accession}


def facts(rows):
    return {'facts':{'us-gaap':{'Revenues':{'units':{'USD':rows}}}}}


def test_fact_selection_preserves_original_and_competing_revision_but_excludes_future():
    rows = [fact('2026-01-01','2026-03-31',100,'2026-05-01'),
            fact('2026-01-01','2026-03-31',100,'2026-05-02','duplicate-vintage'),
            fact('2026-01-01','2026-03-31',101,'2026-05-03','revision'),
            fact('2026-01-01','2026-03-31',999,'2026-11-21','future')]
    selected = actual_candidates(facts(rows), {'report_date':'2026-04-30'})
    assert {(x['value'],x['accession']) for x in selected} == {('100','original'),('101','revision')}


def test_q4_53_week_parent_boundaries_and_no_cross_concept_subtraction():
    annual = fact('2025-01-01','2026-01-07',1000,'2026-02-10'); annual['form']='10-K'
    nine = fact('2025-01-01','2025-09-30',700,'2025-11-01')
    # Neither a 371-day/273-day pairing nor a calendar-year pairing: refuse.
    assert actual_candidates(facts([annual,nine]), {'report_date':'2026-02-09'}) == []
    annual = fact('2024-12-29','2026-01-03',1000,'2026-02-10'); annual['form']='10-K'
    nine = fact('2024-12-29','2025-09-27',700,'2025-11-01')
    selected = actual_candidates(facts([annual,nine]), {'report_date':'2026-02-09'})
    assert len(selected) == 1
    assert selected[0]['value']=='300' and selected[0]['start']=='2025-09-28'
    # A 53rd week can occur in the first nine months rather than in Q4.
    early_extra_week = fact('2024-12-29','2025-10-04',700,'2025-11-01')
    selected = actual_candidates(facts([annual,early_extra_week]), {'report_date':'2026-02-09'})
    assert len(selected) == 1 and selected[0]['start']=='2025-10-05'
    d=facts([annual]); d['facts']['us-gaap']['SalesRevenueNet']={'units':{'USD':[nine]}}
    assert actual_candidates(d, {'report_date':'2026-02-09'}) == []


def test_release_dateline_not_unrelated_8k_earliest_event():
    found=source_issue({'text':'Reports Third Quarter Results. MENLO PARK, October 21, 2026 — financial results.'}, {'filed':'2026-10-21','report_date':'2026-10-19'})
    assert found['date']=='2026-10-21'
    assert source_issue({'text':'Undated financial release'}, {'filed':'2026-10-21','report_date':'2026-10-19'}) is None


def test_adobe_call_is_not_accepted_as_results_publication():
    x=json.loads((ROOT/'earnings/reports/adobe_prep_2026-11-20.json').read_text())
    assert x['results_publication_date'] is None
    assert x['status']=='BLOCKED_UNVERIFIED_RESULTS_PUBLICATION'
