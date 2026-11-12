"""Load reviewed SEC backfill; source dates and review-entry dates stay distinct."""
from pathlib import Path
from datetime import date, datetime, timezone
import json
from psycopg.types.json import Jsonb
from . import store
from .models import DateInterval, Guidance, plain, record_id, money
from .engine import available_guidance, latest_guidance, classify
from .baseline import guidance_cutoff,day_available,aware
from .actuals import Blocked

ROOT=Path(__file__).resolve().parent/'history'


def guidance_record(ticker, row):
    d=dict(row);d.pop('id',None)
    return store.guidance_from(d)


def observation(row):
    target=row['target'];ticker=row['company'];release=row.get('result')
    reason=list(row.get('blocking_reasons',[]))
    actual=store.actual_from({k:v for k,v in row['actual'].items() if k!='id'}) if row.get('actual') else None
    guides=[guidance_record(ticker,g) for g in row.get('guidance_versions',[])]
    selected=None;outcome=None
    if release:
        cutoff=guidance_cutoff(row.get('guidance_anchor_publication_date',release['issued_date']))
        eligible=available_guidance(guides,cutoff,date.fromisoformat(target['start']),date.fromisoformat(target['end']),ticker,metric='quarterly_consolidated_revenue')
        try:selected=latest_guidance(eligible)
        except Blocked as exc:reason.append(exc.code+': '+exc.detail)
    else:
        cutoff=None;reason.append('MISSING_RESULT_RELEASE')
    if actual is None:reason.append('MISSING_ACTUAL')
    if selected and selected.status=='withdrawn':reason.append('GUIDANCE_WITHDRAWN')
    review=row.get('outcome_basis_review',{})
    if review.get('status')!='passed':reason.append('INCOMPARABLE_BASIS: '+review.get('reason','No reviewed guidance-to-result basis'))
    if actual and selected:
        if (actual.company,actual.start,actual.end)!=(ticker,selected.start,selected.end) or (actual.basis,actual.unit)!=(selected.basis,selected.unit):
            reason.append('INCOMPARABLE_BASIS: exact target/basis/unit mismatch')
        if review.get('guidance_id')!=selected.id or review.get('actual_id')!=actual.id:
            reason.append('INCOMPARABLE_BASIS: review is not for selected exact versions')
    if release and actual:
        public=max(day_available(release['issued_date']),day_available(release['filed']),day_available(actual.filed))
    else:public=day_available(target['end'])
    if not reason and selected:
        outcome=classify(actual.value,selected.low,selected.high)
    payload={'company':ticker,'period_start':target['start'],'period_end':target['end'],
       'status':'blocked' if reason else 'eligible','outcome':outcome,
       'public_available_at':public.isoformat(),'guidance_id':selected.id if selected else None,
       'actual_id':actual.id if actual else None,'guidance_cutoff':str(cutoff) if cutoff else None,
       'blocking_reasons':sorted(set(reason)),'source_record':row}
    payload['id']=record_id('reviewed-quarter-observation-v1',payload)
    return payload


def load_all():
    return [observation(r) for path in sorted(ROOT.glob('*.json')) for r in json.loads(path.read_text())['quarters']]


def ingest(conn):
    counts={'inserted':0,'eligible':0,'blocked':0}
    for r in load_all():
        counts[r['status']]+=1
        counts['inserted']+=store.insert(conn,'earnings_historical_observations',{'id':r['id'],
            'company_id':store.company_id(r['company']),'period_start':r['period_start'],'period_end':r['period_end'],
            'guidance_id':r['guidance_id'],'actual_id':r['actual_id'],'outcome':r['outcome'],'status':r['status'],
            'public_available_at':aware(r['public_available_at']),'payload':Jsonb(r)})
    return counts


def stored(conn):
    return [{**row[0],'id':str(row[1]),'recorded_at':row[2].isoformat()} for row in conn.execute('SELECT payload,id,recorded_at FROM earnings_historical_observations')]


if __name__=='__main__':
    from .models import dumps
    with store.connect() as conn:
        conn.execute('SET LOCAL ROLE service_role')
        print(dumps(ingest(conn)))
