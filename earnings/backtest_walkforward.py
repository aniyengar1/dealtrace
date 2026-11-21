"""BACKTEST only: public-date reconstruction. No database or live-ledger writes."""
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, time, timedelta, timezone, date
from decimal import Decimal, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo

from . import baseline, history, smoothed_baseline
from .actuals import Blocked
from .models import dumps

ROOT = Path(__file__).resolve().parent
METHODS = (baseline.METHOD, smoothed_baseline.METHOD, 'uniform', 'always-above')


def load_observations():
    audit_path = ROOT/'reports/scaling_lock_readiness_2027Q1.json'
    audit = json.loads(audit_path.read_text())
    rows = []
    excluded = []
    selected_companies = []
    for company in audit['companies']:
        if company['source_matched_quarters'] < 6:
            excluded.append({'company':company['ticker'], 'reason':'COHORT_BELOW_SIX_SOURCE_MATCHED', 'quarters':company['source_matched_quarters']})
            continue
        selected_companies.append(company['ticker'])
        for r in company['quarter_rows']:
            a, g = r['actual'], r['guidance']
            if r['status'] != 'SOURCE_MATCHED':
                excluded.append({'company':company['ticker'], 'id':r['research_id'], 'reason':r['blocks']})
                continue
            assert a and g and r['outcome'] in baseline.LABELS
            # Training labels require both release publication and exact actual
            # SEC availability; Q4 parents are represented by actual.filed=max.
            available = max(baseline.day_available(d) for d in [a['filed'], r['actual_source']['filed'], r['result_release']['filed'], r['result_release']['report_date']])
            rows.append({'id':r['research_id'], 'company':company['ticker'], 'period_start':a['start'], 'period_end':a['end'], 'status':'eligible', 'outcome':r['outcome'], 'public_available_at':available.isoformat(), 'recorded_at':audit['prepared_at'], 'release_date':r['result_release']['report_date'], 'guidance_id':g['research_version_id'], 'actual_id':a['research_fact_id'], 'guidance_cutoff':r['historical_guidance_cutoff'], 'source_population':'64-company scaling audit', 'source_record':r})
    original = history.load_all()
    eligible_counts = Counter(r['company'] for r in original if r['status']=='eligible')
    for r in original:
        if eligible_counts[r['company']] < 6:
            continue
        if r['status'] != 'eligible':
            excluded.append({'company':r['company'], 'id':r['id'], 'reason':r['blocking_reasons']})
            continue
        s = r['source_record']
        rows.append({**r, 'recorded_at':s['outcome_basis_review']['reviewed_at'], 'release_date':s['guidance_anchor_publication_date'], 'source_population':'original ten-company manual history'})
    selected_companies = sorted(set(selected_companies) | {r['company'] for r in rows})
    return rows, excluded, selected_companies, {'scaling_audit_sha256':hashlib.sha256(audit_path.read_bytes()).hexdigest(), 'manual_history_sha256':hashlib.sha256(''.join(p.read_text() for p in sorted((ROOT/'history').glob('*.json'))).encode()).hexdigest()}


def training_rows(rows, target, prediction_time):
    """No target quarter, later fiscal quarter, or unavailable outcome in pool."""
    cutoff = baseline.aware(prediction_time)
    return [r for r in rows if r['period_end'] < target['period_end'] and baseline.aware(r['public_available_at']) <= cutoff]


def evaluate(rows):
    evaluated, blocked = [], []
    uniform = smoothed_baseline.rates(dict.fromkeys(baseline.LABELS, 0))
    always = {'below':Decimal(0), 'within':Decimal(0), 'above':Decimal(1)}
    for target in sorted(rows, key=lambda r:(r['release_date'],r['company'],r['id'])):
        when = datetime.combine(date.fromisoformat(target['release_date'])-timedelta(days=14),time.min,ZoneInfo(baseline.ZONE))
        prior = training_rows(rows,target,when)
        try:
            raw = baseline.probabilities(target['company'],prior,when,retrospective=True)
        except Blocked as exc:
            blocked.append({'id':target['id'], 'company':target['company'], 'prediction_time':when.isoformat(), 'reason':exc.code})
            continue
        smooth = smoothed_baseline.from_empirical(raw)
        ids = set(raw['historical_ids'])
        assert target['id'] not in ids
        assert ids <= {r['id'] for r in prior}
        probabilities = {baseline.METHOD:raw['probabilities'], smoothed_baseline.METHOD:smooth['probabilities'], 'uniform':uniform, 'always-above':always}
        evaluated.append({'kind':'BACKTEST_NOT_LIVE', 'id':target['id'], 'company':target['company'], 'period_start':target['period_start'], 'period_end':target['period_end'], 'release_date':target['release_date'], 'simulated_prediction_time':when.isoformat(), 'target_public_available_at':target['public_available_at'], 'guidance_id':target['guidance_id'], 'actual_id':target['actual_id'], 'outcome':target['outcome'], 'source_population':target['source_population'], 'selection':{k:raw[k] for k in ['mode','sample_size','company_sample_size','counts','pool_companies','historical_ids','policy']}, 'probabilities':probabilities, 'brier':{m:baseline.brier(p,target['outcome']) for m,p in probabilities.items()}})
    return evaluated, blocked


def summary(rows):
    n=len(rows)
    with localcontext() as ctx:
        ctx.prec=100
        return {'n':n, 'outcomes':dict(Counter(r['outcome'] for r in rows)), 'outcome_shares':{k:Decimal(sum(r['outcome']==k for r in rows))/n if n else None for k in baseline.LABELS}, 'mean_brier':{m:sum((Decimal(r['brier'][m]) for r in rows),Decimal(0))/n if n else None for m in METHODS}, 'own_history_predictions':sum(r['selection']['mode']=='company' for r in rows), 'pooled_predictions':sum(r['selection']['mode']=='pooled' for r in rows)}


def calibration(rows):
    bins={}
    for r in rows:
        for method,p in r['probabilities'].items():
            for label in baseline.LABELS:
                v=Decimal(p[label]);i=min(9,int(v*10));key=(method,label,i)
                cell=bins.setdefault(key,{'method':method,'class':label,'bin':f'[{Decimal(i)/10},{Decimal(i+1)/10}{"]" if i==9 else ")"}','n':0,'predicted_sum':Decimal(0),'observed_count':0})
                cell['n']+=1;cell['predicted_sum']+=v;cell['observed_count']+=r['outcome']==label
    with localcontext() as ctx:
        ctx.prec=100
        return [{**c,'mean_predicted':c['predicted_sum']/c['n'],'observed_frequency':Decimal(c['observed_count'])/c['n']} for _,c in sorted(bins.items())]


def run():
    rows, exclusions, companies, hashes = load_observations()
    # Eight-quarter fixed panels contain no ninth/older rows. Omitting blocked
    # labels cannot admit an older ninth quarter into the frozen eight-row window.
    assert max(Counter(r['company'] for r in rows).values())<=8
    cases, cold = evaluate(rows)
    return {'kind':'BACKTEST_PUBLIC_DATE_RECONSTRUCTION_NOT_LIVE','executed_at':datetime.now(timezone.utc).isoformat(),'source_hashes':hashes,'companies':companies,'source_matched_target_count':len(rows),'target_outcome_counts':dict(Counter(r['outcome'] for r in rows)), 'summary':summary(cases),'per_company':{c:summary([r for r in cases if r['company']==c]) for c in companies},'per_population':{p:summary([r for r in cases if r['source_population']==p]) for p in sorted({r['source_population'] for r in cases})},'calibration':calibration(cases),'evaluated':cases,'insufficient_history':cold,'source_exclusions':exclusions}


def report(d):
    s=d['summary'];lines=['# BACKTEST — quarterly guidance walk-forward','','**Retrospective public-date reconstruction; not live predictions, calibration certification, or an as-recorded operational track record.**','',f"{len(d['companies'])} companies; {d['source_matched_target_count']} eligible source-matched targets; **{s['n']} predictions**; {len(d['insufficient_history'])} insufficient-history exclusions. All four methods are scored on the same targets.",'','| Method | Mean unscaled Brier (lower is better) |','|---|---|']
    for m in METHODS:lines.append(f"| {m} | {s['mean_brier'][m]:.10f} |")
    lines+=['',f"Evaluated outcomes: "+'; '.join(f"{k}: {s['outcomes'].get(k,0)} ({s['outcome_shares'][k]*100:.1f}%)" for k in baseline.LABELS)+'.',f"Company-specific history: {s['own_history_predictions']}; pooled fallback: {s['pooled_predictions']}.",'','## Methodology and limits','','The fixed cohort is the 63 scaling-audit companies with at least six source-matched quarters plus the original ten manual-history companies (all meet six). Rambus is excluded for insufficient consolidated-range history. This is a survivorship-selected cohort of guidance-givers, not the US stock universe. Selection uses today’s coverage; it is not a historically investable universe. Scaling source curation is agent-reviewed research, not completed owner review or production onboarding. All blocked source rows remain exclusions; no ninth quarter is added.','', 'For target results day D, simulate D−14 at New York midnight, preserving the frozen D−15 guidance-selection upper bound. Target guidance was selected in the pinned source audit/manual history; no result-day revision is used. Every training quarter must end strictly before the target quarter and its outcome must be publicly available by the simulated timestamp. Availability is the next New York midnight after the latest result publication, release SEC filing and exact actual SEC filing (including Q4 parent availability). Later restatements cannot enter an earlier fold. Exact IDs, source hashes, availability times and selected historical IDs are in the companion JSON.','', 'Both frozen Python implementations are called unchanged. With ≥6 available own eligible quarters, use own frequencies; otherwise require ≥12 pooled eligible observations across ≥2 companies. The pool contains only earlier and available quarters from this fixed backtest cohort, including the target company; it is larger than the ten-company live pool. The latest eight-quarter cap remains unchanged. In this fixed panel each company has at most eight total quarters, so omitting blocked labels cannot bring an older ninth quarter into a window.','', 'Raw history uses count/N. Smoothed uses (count+1)/(N+3). First two probabilities use half-even rounding to24 decimal places and above receives the residual. Uniform uses the same normalization for one-third; always-above assigns above=1. Unscaled Brier is sum over three classes of (probability−outcome indicator)^2, range0..2. Scores and aggregates use Decimal. No log score, clipping, fitted parameters, or probability tuning is introduced.','', 'Recording/review timestamps are not backdated: this diagnostic explicitly uses the frozen retrospective mode. Today’s labels, fiscal/calendar choices, source selections and basis reviews introduce curation hindsight; historical scheduled-date evidence was not reconstructed. Forecast timestamps are reconstructed from known result dates, not actual historical prediction events. Most cases use pooled fallback because eight quarters provide few six-own-quarter training folds. Overlapping training samples and company outcomes are dependent. Small company samples, heterogeneous pooled firms, acquisition changes, missing source rows, survivorship and guidance practice changes limit generalization. The calibration table is descriptive on this sample; it is not a fresh validation set or proof of predictive quality.','', '## Per-company breakdown','','| Company | n | Own / pool | Below / within / above | Raw history | Smoothed | Uniform | Always above |','|---|---|---|---|---|---|---|---|']
    for c,s in d['per_company'].items():
        means=' | '.join(f"{s['mean_brier'][m]:.6f}" if s['n'] else '—' for m in METHODS)
        lines.append(f"| {c} | {s['n']} | {s['own_history_predictions']} / {s['pooled_predictions']} | "+' / '.join(str(s['outcomes'].get(k,0)) for k in baseline.LABELS)+f' | {means} |')
    lines+=['','## Calibration — fixed bins, no fitting','','Bins are left-inclusive/right-exclusive, except final bin includes1. Each class is evaluated separately; empty cells are omitted. Small cell counts should not be interpreted as reliable calibration estimates.','','| Method | Class | Predicted bin | n | Mean predicted | Observed frequency |','|---|---|---|---|---|---|']
    for c in d['calibration']:lines.append(f"| {c['method']} | {c['class']} | {c['bin']} | {c['n']} | {c['mean_predicted']:.6f} | {c['observed_frequency']:.6f} |")
    lines+=['','## Reproduce','','```sh','.venv/bin/python -m earnings.backtest_walkforward','```','','Outputs: `earnings/reports/backtest_walkforward.json`, this report and a separate `earnings/publication/backtest.json` summary. No database connection, history ingestion, live prediction, or score insert occurs. Re-running changes execution time but the pinned inputs and deterministic case results remain reproducible.']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,default=ROOT/'reports');a=p.parse_args();d=run();a.output_dir.mkdir(parents=True,exist_ok=True)
    (a.output_dir/'backtest_walkforward.json').write_text(dumps(d)+'\n');(a.output_dir/'backtest_walkforward.md').write_text(report(d))
    public={'kind':d['kind'],'executed_at':d['executed_at'],'company_count':len(d['companies']),'source_matched_targets':d['source_matched_target_count'],'summary':d['summary'],'source_hashes':d['source_hashes']}
    (ROOT/'publication/backtest.json').write_text(dumps(public)+'\n');print(dumps(public))
if __name__=='__main__':main()
