"""Repeatable materialization for the Next.js Crosscheck experience."""
import argparse
from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
import sys
import psycopg
from psycopg.types.json import Jsonb
from . import store
from .actuals import parse_companyfacts
from .engine import hurdle, attribution, available_guidance
from .forecast import forecast
from .metrics import parse_metrics, financial_overview, display, evidence
from .evaluate import evaluate
from .models import plain, record_id, dumps
from .registry import companies, load_guidance, ROOT
from .sec import fetch
from .__main__ import persist_calculation, reporting_asof, verify_guidance

REPORT_VERSION = 'company-overview-v1'


def build_report(company, actuals, metric_facts, history, cutoff, evaluation, source_hash, review_through):
    calc = hurdle(company, actuals, history, cutoff)
    if cutoff > date.fromisoformat(review_through) and calc.state == 'ok':
        calc = replace(calc, codes=('GUIDANCE_REVIEW_REQUIRED',), details=(f'Guidance manually reviewed only through {review_through}. Refresh the evidence review before publishing a later forecast.',))
    # Current unresolved scope reviews withhold earlier experimental forecasts too.
    if company.get('comparability', {}).get('blocked') and calc.state == 'ok':
        calc = replace(calc, codes=('INCOMPARABLE_BASIS',), details=('Current acquisition-scope review remains unresolved; historical forecast withheld.',))
    f = forecast(calc, actuals, history)
    gs = available_guidance(history, cutoff, date.fromisoformat(company['period_start']), date.fromisoformat(company['period_end']), company['ticker'])
    guides = []
    for i, g in enumerate(gs):
        change = None
        if i and g.low is not None and gs[i-1].low is not None:
            change = {'low': display(g.low-gs[i-1].low), 'high': display(g.high-gs[i-1].high)}
        guides.append({'id':g.id, **plain(g), 'range_display': 'Withdrawn' if g.status=='withdrawn' else f'{display(g.low)} – {display(g.high)}', 'change': change})
    overview = financial_overview(company, metric_facts, cutoff)
    by_id = {a.id: a for a in actuals}
    selected = {k:evidence(by_id[v]) for k,v in calc.inputs.items() if v in by_id}
    result = {'report_version':REPORT_VERSION, 'as_of':str(cutoff),
              'company':{k:company[k] for k in ('ticker','name','cik','period_start','period_end','fiscal_label','basis','calendar')},
              'overview':overview, 'guidance':guides, 'guidance_review_through':review_through,
              'hurdle':{'id':calc.id,'state':calc.state, **plain(calc)},
              'hurdle_display':{k:display(getattr(calc,k), 'ratio' if k.startswith('growth') else 'USD') for k in ('remaining_low','remaining_high','growth_low','growth_high')},
              'forecast':plain(f), 'forecast_display':{k:display(f.get(k),'ratio' if k in ('observed_growth','prior_remaining_share') else 'USD') for k in ('estimate','benchmark','observed_growth','prior_remaining_share')},
              'selected_inputs':selected, 'evaluation':evaluation,
              'evaluation_display':{k:display(Decimal(evaluation[k]) if evaluation.get(k) is not None else None,'ratio' if 'mape' in k else 'USD') for k in ('mae_usd','mape','benchmark_mae_usd','benchmark_mape')},
              'reporting':plain(reporting_asof(company,cutoff)), 'source_snapshot_sha256':source_hash,
              'coverage_notes':['Revenue is the only forecast/target metric in this milestone.', 'Overview figures are reported US GAAP or explicitly labeled calculations; adjusted figures are not covered.', 'Analyst consensus is not connected.']}
    result['id'] = record_id(REPORT_VERSION,result)
    return result,calc


def save_report(conn, company, report, calc, actuals):
    existing = conn.execute('SELECT payload FROM earnings_company_reports WHERE id=%s',(report['id'],)).fetchone()
    if existing:
        return existing[0],0
    previous = conn.execute('''SELECT payload FROM earnings_company_reports WHERE company_id=%s AND as_of<=%s
                              ORDER BY as_of DESC,created_at DESC,id DESC LIMIT 1''',(store.company_id(company['ticker']),report['as_of'])).fetchone()
    changes = {'previous_report_id':None,'causes':['initial_report'],'input_versions':{}}
    if previous:
        old = previous[0]
        old_calc = store.calculation_from({k:v for k,v in old['hurdle'].items() if k not in ('id','state')})
        changes = {'previous_report_id':old['id'],'causes':attribution(old_calc,calc),
                   'input_versions':{role:{'before':old_calc.inputs.get(role),'after':calc.inputs.get(role)} for role in set(old_calc.inputs)|set(calc.inputs)}}
        if old['overview'] != report['overview']:
            changes['causes'].append('financial_overview_changed')
        for key, cause in [('method', 'forecast_method_changed'), ('assumptions', 'forecast_assumptions_changed'),
                           ('estimate', 'forecast_estimate_changed'), ('verdict', 'forecast_classification_changed')]:
            if old['forecast'].get(key) != report['forecast'].get(key):
                changes['causes'].append(cause)
        if any(old['evaluation'].get(k) != report['evaluation'].get(k) for k in ('sample_size','mae_usd','cases')):
            changes['causes'].append('historical_evaluation_changed')
    report = {**report,'changes':changes}
    persist_calculation(conn,calc,actuals)
    f=report['forecast']
    count=store.insert(conn,'earnings_company_reports',{'id':report['id'],'company_id':store.company_id(company['ticker']),
        'as_of':report['as_of'],'report_version':REPORT_VERSION,'hurdle_id':calc.id,'forecast_id':f['id'],
        'forecast_method':f['method'],'forecast_estimate':Decimal(f['estimate']) if f['estimate'] is not None else None,
        'benchmark_estimate':Decimal(f['benchmark']) if f['benchmark'] is not None else None,
        'forecast_status':f['status'],'payload':Jsonb(report)})
    return report,count


def refresh(tickers, cutoff, refresh_source=False, verify=False):
    registry=companies()
    selected=list(registry) if tickers==['ALL'] else [t.upper() for t in tickers]
    unknown=set(selected)-set(registry)
    if unknown:
        raise ValueError('Unsupported company: '+', '.join(sorted(unknown)))
    for t in selected:
        c=registry[t]
        body,manifest=fetch(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{c["cik"]}.json',refresh=refresh_source)
        payload=json.loads(body,parse_float=Decimal)
        actuals=parse_companyfacts(c,payload); metrics=parse_metrics(c,payload); history=load_guidance(t)
        if verify:
            verify_guidance(t)
        with store.connect() as conn:
            store.register(conn,c)
            new_actuals=sum(store.save_actual(conn,a) for a in actuals)
            new_guides=sum(store.save_guidance(conn,g) for g in history)
            new_metrics=0
            for key,a in metrics:
                new_metrics+=store.insert(conn,'earnings_metric_facts',{'id':a.id,'company_id':store.company_id(t),'metric_key':key,
                    'concept':a.concept,'period_start':a.start,'period_end':a.end,'filed_date':a.filed,
                    'accession':a.accession,'unit':a.unit,'value':a.value,'payload':Jsonb(plain(a))})
            # Evaluation can read existing companies, but never future versions at forecast dates.
            all_actuals={ticker:store.records(conn,ticker)[0] for ticker in registry}
            evaluation=evaluate(registry,all_actuals,cutoff)
            # Read all immutable versions back: an updated SEC payload cannot erase an old fact.
            actuals,history=store.records(conn,t)
            metric_rows=conn.execute('SELECT metric_key,payload FROM earnings_metric_facts WHERE company_id=%s',(store.company_id(t),)).fetchall()
            metrics=[(k,store.actual_from(row)) for k,row in metric_rows]
            reviewed=json.loads((ROOT/'guidance'/f'{t}.json').read_text())['history_review']['cutoff']
            report,calc=build_report(c,actuals,metrics,history,cutoff,evaluation,manifest['sha256'],reviewed)
            report,inserted=save_report(conn,c,report,calc,actuals)
            print(dumps({'company':t,'report_id':report['id'],'as_of':str(cutoff),'forecast':report['forecast']['status'],
                         'verdict':report['forecast']['verdict'],'new_actuals':new_actuals,'new_metrics':new_metrics,
                         'new_guidance':new_guides,'new_report':inserted}))


def main():
    p=argparse.ArgumentParser(description='Refresh immutable reports served by the Next.js Crosscheck UI')
    p.add_argument('command',choices=['refresh','evaluate']);p.add_argument('tickers',nargs='*',default=['ALL'])
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    p.add_argument('--refresh',action='store_true',help='Fetch new SEC companyfacts; retain cached versions')
    p.add_argument('--verify-guidance',action='store_true')
    args=p.parse_args()
    try:
        if args.command=='evaluate':
            registry=companies()
            with store.connect() as conn:
                print(dumps(evaluate(registry,{t:store.records(conn,t)[0] for t in registry},args.as_of)))
        else:
            refresh(args.tickers or ['ALL'],args.as_of,args.refresh,args.verify_guidance)
    except psycopg.Error as exc:
        print(dumps({'database_error':type(exc).__name__,'sqlstate':exc.sqlstate}),file=sys.stderr)
        return 1
    except ValueError as exc:
        print(dumps({'error':str(exc)}),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
