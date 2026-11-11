"""python -m earnings --help"""
import argparse
from datetime import date
from decimal import Decimal
import json
import sys
import psycopg
from psycopg import sql
from pathlib import Path
from bs4 import BeautifulSoup
from . import store
from .actuals import parse_companyfacts, derive_remaining, snapshot, exactly, Blocked
from .engine import hurdle, attribution, outcomes
from .models import dumps, plain, Policy, DateInterval
from .registry import companies, load_guidance
from .sec import fetch


def persist_calculation(conn, result, actuals):
    by_id={a.id:a for a in actuals}
    if 'prior_remaining' in result.inputs:
        derived=derive_remaining(by_id[result.inputs['prior_annual']],by_id[result.inputs['prior_ytd']])
        if derived.id!=result.inputs['prior_remaining']:
            raise ValueError('Derived input identity mismatch')
        store.save_actual(conn,derived)
    store.save_calculation(conn,result)


def verify_guidance(ticker,refresh=False):
    results=[]
    for g in load_guidance(ticker):
        body,manifest=fetch(g.source_url,refresh=refresh)
        source=BeautifulSoup(body,'html.parser').get_text(' ',strip=True)
        found=' '.join(g.quote.split()) in ' '.join(source.split())
        results.append({'guidance_id':g.id,'source_url':g.source_url,'sha256':manifest['sha256'],'quote_verified':found})
        if not found:
            raise ValueError(f'{ticker}: guidance quote missing from {g.source_url}')
    return results


def reporting_asof(company,cutoff):
    report=dict(company['next_report'])
    if date.fromisoformat(report['source_date'])>cutoff:
        report={'type':report['type'],'date':None,'status':'unverified','verification_gap':'Announcement was not public by this cutoff'}
    annual=dict(company['annual_result'])
    if date.fromisoformat(annual['source_date'])>cutoff:
        annual={'type':annual['type'],'status':'unverified','verification_gap':'Annual reporting-window source was not public by this cutoff'}
    return {'company':company['ticker'],'as_of':cutoff,'next_report':report,'annual_result':annual}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Crosscheck deterministic annual revenue guidance pipeline')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('migrate',help='Apply pending repository migrations; inspect first when sharing a DB')
    for command in ('ingest','load-guidance','calculate','verify-guidance','report-dates','outcome','verify-real'):
        p=sub.add_parser(command);p.add_argument('tickers',nargs='+',help='Approved tickers, or ALL')
        if command in ('ingest','verify-guidance'):p.add_argument('--refresh',action='store_true')
        if command in ('calculate','report-dates','outcome'):p.add_argument('--as-of',type=date.fromisoformat,required=True)
        if command=='calculate':
            p.add_argument('--actual-days',type=int,default=135);p.add_argument('--guidance-days',type=int,default=150)
            p.add_argument('--policy-version',default='manual-freshness-v1')
        if command=='outcome':
            p.add_argument('--result-issued',required=True,help='ISO date, or JSON date interval')
            p.add_argument('--result-accession',required=True);p.add_argument('--result-url',required=True)
            p.add_argument('--not-comparable',action='store_true')
    p=sub.add_parser('inspect');p.add_argument('id')
    p=sub.add_parser('compare');p.add_argument('before');p.add_argument('after')
    args=parser.parse_args(argv)
    if args.command=='migrate':
        from db.migrate import run
        from dotenv import load_dotenv
        load_dotenv();print(dumps({'applied':run()}));return
    registry=companies()
    if args.command in ('inspect','compare'):
        with store.connect() as conn:
            if args.command=='inspect':
                for table in ('hurdle_calculations','earnings_actuals','guidance_versions','guidance_outcomes'):
                    row=conn.execute(sql.SQL('SELECT payload FROM {} WHERE id=%s').format(sql.Identifier(table)),(args.id,)).fetchone()
                    if row:
                        print(dumps({'id':args.id,'table':table,'record':row[0]}));return
                raise ValueError('Record not found')
            records=[]
            for identifier in (args.before,args.after):
                row=conn.execute('SELECT payload FROM hurdle_calculations WHERE id=%s',(identifier,)).fetchone()
                if not row:raise ValueError('Calculation not found')
                records.append(store.calculation_from(row[0]))
            if records[0].company!=records[1].company:raise ValueError('Cannot compare different companies')
            print(dumps({'attribution':attribution(*records)}));return
    tickers=list(registry) if args.tickers==['ALL'] else [t.upper() for t in args.tickers]
    errors=False
    for ticker in tickers:
        try:
            company=registry[ticker]
            if args.command=='report-dates':
                print(dumps(reporting_asof(company,args.as_of)));continue
            if args.command=='verify-real':
                from .verification import verify_real
                print(dumps(verify_real(ticker)));continue
            if args.command=='verify-guidance':
                print(dumps({'company':ticker,'verified':verify_guidance(ticker,args.refresh)}));continue
            with store.connect() as conn:
                store.register(conn,company)
                if args.command=='ingest':
                    body,manifest=fetch(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{company["cik"]}.json',refresh=args.refresh)
                    records=parse_companyfacts(company,json.loads(body,parse_float=Decimal))
                    count=sum(store.save_actual(conn,a) for a in records)
                    print(dumps({'company':ticker,'inserted':count,'records':len(records),'source':manifest}));continue
                if args.command=='load-guidance':
                    history=load_guidance(ticker)
                    count=sum(store.save_guidance(conn,g) for g in history)
                    print(dumps({'company':ticker,'inserted':count,'versions':len(history)}));continue
                actuals,history=store.records(conn,ticker)
                if args.command=='outcome':
                    a=exactly(snapshot(actuals,args.as_of),date.fromisoformat(company['period_start']),date.fromisoformat(company['period_end']),ticker,company['concept'],company['basis'])
                    issued=DateInterval.read(json.loads(args.result_issued) if args.result_issued.startswith('{') else args.result_issued)
                    r=outcomes(company,a,history,cutoff=args.as_of,result_issued=issued,
                        result_source={'accession':args.result_accession,'url':args.result_url},comparable=not args.not_comparable)
                    store.save_outcome(conn,r,a);print(dumps(r));continue
                policy=Policy(args.policy_version,args.actual_days,args.guidance_days)
                if policy!=Policy() and args.policy_version==Policy().version:
                    raise ValueError('Changed manual thresholds require a new --policy-version')
                r=hurdle(company,actuals,history,args.as_of,policy)
                persist_calculation(conn,r,actuals)
                print(dumps({'id':r.id,'state':r.state,**plain(r)}))
        except (ValueError,KeyError,Blocked) as exc:
            errors=True
            print(dumps({'company':ticker,'error':str(exc)}),file=sys.stderr)
    return 1 if errors else 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except psycopg.Error as exc:
        # Never echo a connection string or driver traceback containing credentials.
        print(dumps({'database_error':type(exc).__name__,'sqlstate':exc.sqlstate}),file=sys.stderr)
        raise SystemExit(1)
