"""python -m earnings.predict --lock. No backdated/as-of live insertion path."""
import argparse,json,sys
from datetime import date,timedelta,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from uuid import uuid4
import psycopg
from . import store,history
from .registry import companies
from .engine import available_guidance,latest_guidance
from .baseline import probabilities,guidance_cutoff,METHOD
from .live import announcement,deadline,refresh_announcement,publication_check,insert_prediction
from .actuals import Blocked
from .models import plain,dumps


def run(conn,registry,*,announcement_loader=announcement,refresh=refresh_announcement,publication=publication_check):
    # Use application write privileges even with a local owner connection.
    conn.execute('SET LOCAL ROLE service_role');loaded=history.ingest(conn)
    now=conn.execute('SELECT clock_timestamp()').fetchone()[0].astimezone(timezone.utc)
    result={'execution_started_at':now.isoformat(),'clock_source':'PostgreSQL clock_timestamp()',
            'method_version':METHOD,'history_ingestion':loaded,'locked':[],'skipped':[]}
    observations=history.stored(conn)
    for ticker,c in registry.items():
        target=c['quarter_targets'][-1]
        try:
            existing=conn.execute('SELECT id,made_at FROM earnings_live_predictions WHERE company_id=%s AND period_start=%s AND period_end=%s AND metric=%s AND method_version=%s',
                (store.company_id(ticker),target['start'],target['end'],'quarterly_consolidated_revenue',METHOD)).fetchone()
            if existing:
                result['skipped'].append({'company':ticker,'code':'ALREADY_LOCKED','id':str(existing[0]),'made_at':existing[1].isoformat()});continue
            e=announcement_loader(c);due=deadline(e)
            if now>=due:raise Blocked('LOCK_DEADLINE_PASSED','Publication deadline has passed; no retrospective live prediction')
            if due-now>timedelta(days=14):
                result['skipped'].append({'company':ticker,'code':'OUTSIDE_14_DAY_WINDOW','release_date':e['release_date'],
                    'next_eligibility_at':(due-timedelta(days=14)).isoformat(),'deadline':due.isoformat(),'announcement_evidence':e});continue
            e=refresh(c,e)
            actuals,guides=store.records(conn,ticker)
            current=latest_guidance(available_guidance(guides,now.astimezone(ZoneInfo('America/New_York')).date(),date.fromisoformat(target['start']),date.fromisoformat(target['end']),ticker,metric='quarterly_consolidated_revenue'))
            if current.status=='withdrawn':raise Blocked('GUIDANCE_WITHDRAWN','Current public target guidance is withdrawn')
            g=latest_guidance(available_guidance(guides,guidance_cutoff(e['release_date']),date.fromisoformat(target['start']),date.fromisoformat(target['end']),ticker,metric='quarterly_consolidated_revenue'))
            if g.status=='withdrawn':raise Blocked('GUIDANCE_WITHDRAWN','Frozen horizon guidance is withdrawn')
            scope=target.get('growth_comparability',{})
            if scope.get('blocked',True):
                raise Blocked('INCOMPARABLE_BASIS','Prospective baseline scope review unresolved: '+scope.get('reason','No review'))
            from .models import Policy
            policy=Policy()
            if (now.date()-g.issued.end).days>policy.guidance_days:
                raise Blocked('STALE_INPUT',f'Manual {policy.version}: guidance_days={policy.guidance_days} exceeded')
            recent=[a for a in actuals if a.filed<=now.date() and a.end<=now.date()]
            if not recent or (now.date()-max(a.end for a in recent)).days>policy.actual_days:
                raise Blocked('STALE_INPUT',f'Manual {policy.version}: actual_days={policy.actual_days} exceeded or no available actual')
            b=probabilities(ticker,observations,now)
            checked=publication(c,target)
            if checked['status']!='not_observed':raise Blocked('PUBLICATION_CHECK_BLOCKED',json.dumps(checked,sort_keys=True))
            with conn.transaction():
                locked=insert_prediction(conn,c,target,g,b,e,checked)
            if locked:result['locked'].append({'company':ticker,**locked,'guidance_id':g.id,'baseline':plain(b),'announcement':e,'publication_check':checked})
            else:result['skipped'].append({'company':ticker,'code':'ALREADY_LOCKED_CONCURRENTLY'})
        except Blocked as exc:result['skipped'].append({'company':ticker,'code':exc.code,'reason':exc.detail,'unverified_release_lead':c['next_report'].get('date')})
        except (ValueError,psycopg.Error) as exc:
            result['skipped'].append({'company':ticker,'code':'LOCK_VALIDATION_FAILED','error_type':type(exc).__name__})
    result['execution_finished_at']=conn.execute('SELECT clock_timestamp()').fetchone()[0].astimezone(timezone.utc).isoformat()
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--lock',action='store_true',required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.output and args.output.exists():parser.error('--output already exists; choose a new execution record')
    try:
        with store.connect() as conn:r=run(conn,companies())
        output=args.output or Path('data/cache/earnings/lock-runs')/(r['execution_started_at'].replace(':','-')+'-'+str(uuid4())+'.json')
        output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('x') as stream:stream.write(dumps(r)+'\n')
        print(dumps({**r,'execution_record':str(output)}))
    except psycopg.Error as exc:
        print(dumps({'database_error':type(exc).__name__,'sqlstate':exc.sqlstate}),file=sys.stderr);raise SystemExit(1)
