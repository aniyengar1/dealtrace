"""Append reviewed outcomes/corrections against locked guidance; never rewrite locks."""
import argparse,json,sys
from datetime import date,datetime,time,timezone
from decimal import localcontext
from pathlib import Path
from zoneinfo import ZoneInfo
import psycopg
from psycopg.types.json import Jsonb

from . import store
from .models import money,digest,plain,dumps
from .baseline import aware,brier
from .engine import classify
from .actuals import Blocked
from .quarters import review_block


def verify_sources(review):
    """Only SEC transport; verify and ingest exact reviewed companyfacts versions."""
    from .sec import fetch
    from .history_audit import normalized
    from urllib.parse import urlparse
    from .baseline import day_available
    actual=review['actual'];parents=review.get('actual_parents',[])
    records=parents if actual.get('parents') else [actual]
    for a in records:
        if urlparse(a['source_url']).path.find('/api/xbrl/companyfacts/')!=0:
            raise Blocked('MISSING_PERIOD','Actual must trace to SEC companyfacts, including derivation parents')
        body,_=fetch(a['source_url'],refresh=True)
        facts=json.loads(body,parse_float=money)['facts']['us-gaap'][a['concept']]['units'][a['unit']]
        if not any(f.get('start')==a['start'] and f['end']==a['end'] and f['accn']==a['accession'] and f['filed']==a['filed'] and money(f['val'])==money(a['value']) for f in facts):
            raise Blocked('MISSING_PERIOD','Reviewed actual version not found in fresh SEC companyfacts')
    if actual.get('parents'):
        from .actuals import derive_q4
        parsed=[store.actual_from({k:v for k,v in a.items() if k!='id'}) for a in parents]
        if len(parsed)!=2:raise Blocked('MISSING_PERIOD','Exactly two compatible Q4 derivation parents required')
        annual=max(parsed,key=lambda a:a.end);ytd=min(parsed,key=lambda a:a.end)
        from .registry import companies
        derived=derive_q4(annual,ytd,expected_ytd_end=ytd.end,expected_annual_end=annual.end,
                          calendar=companies()[actual['company']]['calendar'])
        if derived.id!=actual['id']:raise Blocked('MISSING_PERIOD','Derived Q4 does not reproduce the reviewed actual')
    result=review['result_source'];body,_=fetch(result['url'],refresh=True)
    if result['quote'] not in normalized(body):raise Blocked('MISSING_PERIOD','Result publication evidence quote absent from SEC source')
    # Filing acceptance precision must be independently sourced, not asserted.
    # Default reviews use day precision, with a deliberately conservative lower bound.
    if review.get('actual_filing_accepted_at'):
        raise Blocked('UNVERIFIED_ACCEPTANCE_TIME','Use conservative filing-day precision; exact acceptance verification is not implemented')
    if not result.get('issued_date') or not result.get('issuance_date_quote') or result['issuance_date_quote'] not in normalized(body):
        raise Blocked('MISSING_PUBLICATION_TIMING','SEC release dateline and exact literal date quote required')
    lower=datetime.combine(date.fromisoformat(result['issued_date']),time.min,ZoneInfo('America/New_York')).astimezone(timezone.utc)
    if aware(review['first_result_publication_lower_bound'])>lower:
        raise Blocked('UNVERIFIED_PUBLICATION_TIME','No exact publication verification: use start of the dated release day, never a call time')
    if aware(review['evidence_available_at'])<max(day_available(actual['filed']),day_available(result['filed_date'])):
        raise Blocked('MISSING_PERIOD','Evidence availability must respect both day-precision SEC filing intervals')


def evaluate(prediction,review,now):
    now=aware(now);made=aware(prediction['made_at']);locked=prediction['snapshot']['locked_guidance']
    actual=review.get('actual');basis=review.get('outcome_basis_review',{})
    if not actual:raise Blocked('MISSING_PERIOD','No exact reported revenue actual and source evidence')
    parsed=store.actual_from({k:v for k,v in actual.items() if k!='id'})
    if parsed.id!=actual.get('id'):raise Blocked('MISSING_PERIOD','Actual ID does not reproduce its financial/provenance payload')
    if actual.get('id')!=basis.get('actual_id') or basis.get('guidance_id')!=prediction['guidance_id']:
        raise Blocked('INCOMPARABLE_BASIS','Outcome review must bind exact actual and locked guidance versions')
    blocked=review_block(basis,now.date())
    if blocked:raise Blocked('INCOMPARABLE_BASIS',blocked)
    if (actual['company'],actual['start'],actual['end'])!=(locked['company'],locked['start'],locked['end']) or (actual['basis'],actual['unit'])!=(locked['basis'],locked['unit']):
        raise Blocked('INCOMPARABLE_BASIS','Actual and locked target period/basis/unit differ')
    if not review.get('first_result_publication_lower_bound') or not review.get('evidence_available_at'):
        raise Blocked('MISSING_PUBLICATION_TIMING','Need first results publication lower boundary and actual evidence availability, not call/SEC dates alone')
    public=aware(review['first_result_publication_lower_bound']);available=aware(review['evidence_available_at'])
    accepted=aware(review['actual_filing_accepted_at']) if review.get('actual_filing_accepted_at') else datetime.combine(date.fromisoformat(actual['filed']),time.min,ZoneInfo('America/New_York')).astimezone(timezone.utc)
    earliest=min(public,accepted)
    if made>=earliest:raise Blocked('NOT_PROSPECTIVE','Results could have been public before this prediction; no live score')
    if available>now or accepted>now or date.fromisoformat(actual['filed'])>now.astimezone(ZoneInfo('America/New_York')).date():
        raise Blocked('MISSING_PERIOD','Actual/evidence is not publicly available yet')
    if not actual.get('accession') or not actual.get('source_url','').startswith('https://data.sec.gov/') and not actual.get('source_url','').startswith('https://www.sec.gov/Archives/'):
        raise Blocked('MISSING_PERIOD','SEC actual provenance required')
    result=review.get('result_source',{})
    if not result.get('accession') or not result.get('url','').startswith('https://www.sec.gov/Archives/'):
        raise Blocked('MISSING_PERIOD','Dated first-result SEC evidence required')
    if not result.get('filed_date') or date.fromisoformat(result['filed_date'])>now.date() or not result.get('quote'):
        raise Blocked('MISSING_PERIOD','Result source needs an available filing date and publication evidence quote')
    outcome=classify(money(actual['value']),money(locked['low']),money(locked['high']))
    probabilities={k:money(prediction['p_'+k]) for k in ['below','within','above']}
    score=brier(probabilities,outcome)
    snapshot={'guidance_id':prediction['guidance_id'],'actual_publication_lower_bound':earliest.isoformat(),
        'evidence_available_at':available.isoformat(),'review':review,'locked_guidance':locked,
        'probabilities':plain(probabilities),'formula':'sum((p_k - 1[outcome=k])^2), unscaled, range 0..2'}
    return {'status':'scored','outcome':outcome,'brier':score,'snapshot':snapshot,
            'evidence_hash':digest({'guidance_id':prediction['guidance_id'],'actual_id':actual['id'],
              'result_source':result,'basis':{k:v for k,v in basis.items() if k not in ('reviewed_at','verifier')},
              'first_result_publication_lower_bound':review['first_result_publication_lower_bound']})}


def save(conn,prediction_id,evaluated):
    # Serialize correction chains without UPDATE privileges or mutable lock rows.
    conn.execute('SELECT pg_advisory_xact_lock(10303,hashtext(%s))',(prediction_id,))
    previous=conn.execute('SELECT id,evidence_hash FROM earnings_live_results WHERE prediction_id=%s ORDER BY scored_at DESC,id DESC LIMIT 1',(prediction_id,)).fetchone()
    row=conn.execute('''INSERT INTO earnings_live_results(prediction_id,evidence_hash,status,outcome,brier,supersedes_id,snapshot)
      VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(prediction_id,evidence_hash) DO NOTHING RETURNING id,scored_at''',
      (prediction_id,evaluated['evidence_hash'],evaluated['status'],evaluated['outcome'],evaluated['brier'],previous[0] if previous else None,Jsonb(plain(evaluated['snapshot'])))).fetchone()
    return {'id':str(row[0]),'scored_at':row[1].astimezone(timezone.utc).isoformat(),'supersedes_id':str(previous[0]) if previous else None} if row else None


def prediction_rows(conn):
    return [{'id':str(r[0]),'made_at':r[1].isoformat(),'guidance_id':str(r[2]),'snapshot':r[3],
             'p_below':r[4],'p_within':r[5],'p_above':r[6]} for r in conn.execute('SELECT id,made_at,guidance_id,snapshot,p_below,p_within,p_above FROM earnings_live_predictions ORDER BY made_at,id')]


def run(conn,review_dir):
    conn.execute('SET LOCAL ROLE service_role');now=conn.execute('SELECT clock_timestamp()').fetchone()[0]
    result={'execution_started_at':now.astimezone(timezone.utc).isoformat(),'scored':[],'blocked':[]}
    for prediction in prediction_rows(conn):
        files=list(review_dir.glob(prediction['id']+'*.json'));reviews=[]
        if not files:
            result['blocked'].append({'prediction_id':prediction['id'],'code':'MISSING_REVIEWED_OUTCOME'});continue
        for path in files:
            try:reviews.append((path,json.loads(path.read_text())))
            except (ValueError,OSError):result['blocked'].append({'prediction_id':prediction['id'],'code':'INVALID_REVIEW_FILE','file':path.name})
        for path,review in sorted(reviews,key=lambda pair:(pair[1].get('evidence_available_at',''),pair[0].name)):
            try:
                verify_sources(review);evaluated=evaluate(prediction,review,now)
                with conn.transaction():
                    for a in review.get('actual_parents',[]):store.save_actual(conn,store.actual_from({k:v for k,v in a.items() if k!='id'}))
                    store.save_actual(conn,store.actual_from({k:v for k,v in review['actual'].items() if k!='id'}))
                    saved=save(conn,prediction['id'],evaluated)
                result['scored'].append({'prediction_id':prediction['id'],'outcome':evaluated['outcome'],'brier':str(evaluated['brier']),'inserted':saved})
            except Blocked as exc:result['blocked'].append({'prediction_id':prediction['id'],'code':exc.code,'reason':exc.detail})
            except (ValueError,KeyError,TypeError,OSError,RuntimeError,psycopg.Error) as exc:result['blocked'].append({'prediction_id':prediction['id'],'code':'SCORING_VALIDATION_FAILED','error_type':type(exc).__name__})
    result['execution_finished_at']=conn.execute('SELECT clock_timestamp()').fetchone()[0].astimezone(timezone.utc).isoformat()
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--review-dir',type=Path,default=Path('earnings/scoring_reviews'));p.add_argument('--output',type=Path);args=p.parse_args()
    if args.output and args.output.exists():p.error('--output already exists; choose a new execution record')
    try:
        with store.connect() as conn:r=run(conn,args.review_dir)
        if args.output:
            with args.output.open('x') as stream:stream.write(dumps(r)+'\n')
        print(dumps(r))
    except psycopg.Error as exc:
        print(dumps({'database_error':type(exc).__name__,'sqlstate':exc.sqlstate}),file=sys.stderr);raise SystemExit(1)
