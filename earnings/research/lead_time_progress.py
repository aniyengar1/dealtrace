"""Reproduce the bounded Nov22 date-study update; no network or database."""
from copy import deepcopy
from datetime import date,datetime,timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def build():
    prior=json.loads((ROOT/'reports/lead_time_followup_2026-11-20.json').read_text())
    additions=json.loads((ROOT/'research/scaling_2027q1/lead_time_additions_20261122.json').read_text())
    audit=ROOT/'reports/scaling_lock_readiness_2027Q1.json'
    assert hashlib.sha256(audit.read_bytes()).hexdigest()==prior['financial_audit_sha256']
    companies=deepcopy(prior['companies']);by={c['ticker']:c for c in companies}
    for pair in additions['pairs']:
        c=by[pair['ticker']]
        assert pair['scheduled_release'] in c['missing_regular_release_dates']
        c['pairs'].append({**pair,'lead_days':(date.fromisoformat(pair['scheduled_release'])-date.fromisoformat(pair['issued'])).days})
        c['missing_regular_release_dates'].remove(pair['scheduled_release'])
        c['verified_matching_pairs']=len({p['scheduled_release'] for p in c['pairs']})
        c['complete']=c['verified_matching_pairs']==4
        gaps=sorted(Decimal(p['lead_days']) for p in c['pairs'])
        c['typical_gap_days']=str((gaps[1]+gaps[2])/2) if c['complete'] else None
        c['range_days']=[str(gaps[0]),str(gaps[-1])]
        if c['complete']:c['gap']=None
    return {'kind':'HISTORICAL_LEAD_TIME_PROGRESS_NOT_LIVE_ELIGIBILITY','prepared_at':datetime.now(timezone.utc).isoformat(),
            'financial_audit_sha256':prior['financial_audit_sha256'],'previous_complete_count':prior['complete_count'],
            'complete_count':sum(c['complete'] for c in companies),'remaining_count':sum(not c['complete'] for c in companies),
            'new_complete':[c['ticker'] for c in companies if c['complete'] and not next(x for x in prior['companies'] if x['ticker']==c['ticker'])['complete']],
            'companies':companies,'new_pairs':additions['pairs'],'attempts':additions['attempts'],'remaining_selected_gaps':additions['remaining_selected_gaps']}


def main():
    r=build();p=ROOT/'reports/lead_time_followup_2026-11-22'
    p.with_suffix('.json').write_text(json.dumps(r,indent=2)+'\n')
    lines=['# Historical announcement lead-time progress — November22UTC','',f"**{r['complete_count']}/64 complete four-quarter matching studies, up from{r['previous_complete_count']}; {r['remaining_count']} remain incomplete.** Newly complete: {', '.join(r['new_complete'])}.",'','Research only. No production company onboarding, guidance/history import, announcement promotion, lock, financial/backtest input revision or future2027 date verification. Selection prioritized the six remaining one-pair issuer studies (excluding the separate LITE schedule mismatch) and was recorded before the direct-HTTP article pass. Search excerpts were discovery leads only. Six dated full company-hosted articles were retrieved/reviewed and original bodies/hashes/check and fetch timestamps preserved. All106 prior pair records remain semantically identical; the prior24-company report and financial audit remain unchanged.','', '| Issuer | Matched quarters | Median announcement lead | Range |','|---|---|---|---|']
    for c in r['companies']:
        if c['ticker'] in r['new_complete']:lines.append(f"| {c['ticker']} | 4/4 | {c['typical_gap_days']} days | {'–'.join(c['range_days'])} days |")
    lines+=['','## Added dated source evidence','','| Issuer | Issued | Matching SEC results date | Lead days | Official source |','|---|---|---|---|---|']
    for x in r['new_pairs']:
        gap=(date.fromisoformat(x['scheduled_release'])-date.fromisoformat(x['issued'])).days
        lines.append(f"| {x['ticker']} | {x['issued']} | {x['scheduled_release']} | {gap} | [Full announcement]({x['url']}) |")
    lines+=['','All article publication sentences explicitly concern financial-results release, not just calls. Issuance datelines are checked separately from results dates. The companion JSON preserves quotes, raw-body SHA256, true retrieval/check times, matched SEC-result evidence and any completed-period disclosure blocks. Typical median requires all four matching regular-release dates. These are regular-results announcement gaps, not proof of earliest public financial information or live lock eligibility.','', '## Remaining selected gaps','']
    for t,gap in r['remaining_selected_gaps'].items():lines.append(f'- **{t}:** {gap}')
    lines+=['','The selection was bounded, not an exhaustive search of all38 incomplete studies. Do not equate an access failure or uncounted source with no announcement. No third-party reprint, unsupported date, inferred timestamp or cross-host source expansion was used to fill a gap. Ichor search leads are kept outside counted evidence until the preservation gap is resolved.','', 'LITE remains3/4 with its November5 scheduled versus November2 actual release discrepancy. DOCN/ONTO preliminary-result blocks remain intact. Lead times alone do not clear fresh already-public-results checks or comparability.','', '## Reproduce','','`.venv/bin/python -m earnings.research.lead_time_progress` rebuilds from the committed prior report and curated addition manifest without network/database access. Existing research/cache failure records and the previous report are preserved.']
    p.with_suffix('.md').write_text('\n'.join(lines)+'\n')
    print({k:r[k] for k in ('complete_count','new_complete','remaining_count')})


if __name__=='__main__':main()
