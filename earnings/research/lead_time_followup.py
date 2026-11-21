"""Lead-time research only; preserve the pinned financial/backtest input audit."""
import json,hashlib,re
from pathlib import Path
from datetime import date,datetime,timezone
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1]

def run():
    audit_path=ROOT/'reports/scaling_lock_readiness_2027Q1.json';audit=json.loads(audit_path.read_text());pairs=json.loads((ROOT/'research/scaling_2027q1/announcement_pairs.json').read_text())['pairs'];companies=[]
    for c in audit['companies']:
        selected=[];mismatches=[]
        for p in pairs:
            if p['ticker']!=c['ticker']:continue
            if p['scheduled_release'] in c['last_four_results_dates']:
                item={**p,'lead_days':(date.fromisoformat(p['scheduled_release'])-date.fromisoformat(p['issued'])).days}
                target=next(r for r in c['quarter_rows'] if r['result_release']['report_date']==p['scheduled_release'])
                item['completed_period_disclosure_blocks']=[b for b in target['blocks'] if 'EARLIER_COMPLETED_PERIOD' in b]
                selected.append(item)
            elif 'SCHEDULE MISMATCH' in p.get('notes',''):
                actual=next(r for r in c['quarter_rows'] if r['result_release']['report_date']=='2026-11-02')
                mismatches.append({**p,'actual_publication_date':'2026-11-02','actual_release_evidence':actual['actual_source']})
        bydate={p['scheduled_release']:p for p in selected};v=sorted(Decimal(p['lead_days']) for p in bydate.values());median=(v[1]+v[2])/2 if len(v)==4 else None
        companies.append({'ticker':c['ticker'],'company':c['company'],'verified_matching_pairs':len(bydate),'complete':len(bydate)==4,'previously_complete':c['verified_last_four_pairs']==4,'typical_gap_days':str(median) if median is not None else None,'range_days':[str(v[0]),str(v[-1])] if v else None,'pairs':list(bydate.values()),'missing_regular_release_dates':[x for x in c['last_four_results_dates'] if x not in bydate],'schedule_mismatches':mismatches,'gap':('Nov5 scheduled versus Nov2 actual: earlier results disclosed with merger; replacement advance notice not established.' if mismatches else 'Unretrieved qualifying official articles or incomplete archive discovery; prior timestamped failures remain preserved.') if len(bydate)<4 else None})
    attempts=[]
    for name in ['leadtime-followup-metadata.json','leadtime-pdf-metadata.json','leadtime-extra-metadata.json']:
        attempts+=json.loads((Path('data/cache/earnings/scaling-2027q1-dates')/name).read_text())
    result={'kind':'ANNOUNCEMENT_LEAD_TIME_RESEARCH_NOT_LOCK_EVIDENCE','prepared_at':datetime.now(timezone.utc).isoformat(),'financial_audit_sha256':hashlib.sha256(audit_path.read_bytes()).hexdigest(),'complete_count':sum(c['complete'] for c in companies),'previous_complete_count':audit['complete_four_announcement_pairs'],'new_complete':[c['ticker'] for c in companies if c['complete'] and not c['previously_complete']],'remaining_count':sum(not c['complete'] for c in companies),'companies':companies,'followup_attempts':attempts}
    path=ROOT/'reports/lead_time_followup_2026-11-20';path.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Announcement lead-time follow-up — November20,2026','',f"**{result['complete_count']}/64 verified four-quarter matching studies, up from {result['previous_complete_count']}; {result['remaining_count']} incomplete.** Newly complete: {', '.join(result['new_complete'])}.",'','All dates are historical. No 2027 date, live announcement record, guidance record, historical input, or lock was imported/changed. The prior financial audit remains pinned for backtest reproduction. We prioritized the fourteen partially completed studies because one to three missing official articles could complete each. All original64 access/discovery records are preserved; the remaining studies are not certified exhaustive news searches.','', 'A pair uses the full dated company-hosted article or PDF, not a search excerpt. Gap is announcement issuance day to the matching regular SEC results-release day, in calendar dates; median requires all four. Retrieval/observation timestamps and hashes distinguish rendered evidence from original HTTP/PDF bytes. A regular release is not necessarily the first public financial indication. Completed-period preliminary/in-line/reaffirmation blocks from the financial audit are repeated per quarter in JSON. DOCN Q2 had preliminary results Jul7, before the Jul21 date announcement; ONTO Q1 had preliminary results Apr16, before a possible17-day window for May5. These lead times do not establish historical lock eligibility.','', '**LITE discrepancy:** October5 announcement scheduled November5,2026; SEC results were actually published November2 alongside merger news. It remains3/4 matching pairs with an explicit schedule discrepancy, not a fabricated November2 announcement. Do not use a scheduled date without the fresh already-public-results check. EPAM announcements promise a release before the call; historical actual publication dates are verified separately from SEC releases. This does not promote those announcements to standalone future timing evidence.','', '| Company | Matched /4 | Typical median days | Range | Unresolved actual release dates / gap |','|---|---|---|---|---|']
    for c in sorted(companies,key=lambda c:(not c['complete'],c['ticker'])):
        lines.append(f"| {c['ticker']} | {c['verified_matching_pairs']} | {c['typical_gap_days'] or 'Unverified'} | {'–'.join(c['range_days']) if c['range_days'] else 'Unverified'} | {', '.join(c['missing_regular_release_dates']) or '—'} {c['gap'] or ''} |")
    lines+=['','## Added full-source evidence','','| Company | Announcement issued | Scheduled results | Source |','|---|---|---|---|']
    for p in pairs[85:]:lines.append(f"| {p['ticker']} | {p['issued']} | {p['scheduled_release']} | [Official source]({p['url']}) {p.get('notes','')} |")
    lines+=['','## Reproduce','','`.venv/bin/python -m earnings.research.lead_time_followup` uses the committed source selections and pinned financial audit, with local cached request metadata. It makes no provider or network calls and has no database access.']
    path.with_suffix('.md').write_text('\n'.join(lines)+'\n');print({k:result[k] for k in ['complete_count','new_complete','remaining_count']})
if __name__=='__main__':run()
