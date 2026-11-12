"""PostgreSQL persistence: content-addressed, append-preserving application inserts (not DB locks)."""
import os
from datetime import date
from decimal import Decimal
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from dotenv import load_dotenv
from .models import Actual, Guidance, DateInterval, Calculation, Policy, digest, plain, record_id


def connect():
    load_dotenv()
    return psycopg.connect(os.environ['DATABASE_URL'])


def company_id(ticker):
    return record_id('company-v1', ticker)


def register(conn, company):
    existing = conn.execute('SELECT cik FROM companies WHERE ticker=%s', (company['ticker'],)).fetchone()
    if existing and existing[0] != company['cik']:
        raise ValueError('Existing company CIK cannot change without explicit entity reconciliation')
    conn.execute('''INSERT INTO companies(id,ticker,cik,name,config) VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT(ticker) DO UPDATE SET config=EXCLUDED.config, name=EXCLUDED.name''',
                 (company_id(company['ticker']),company['ticker'],company['cik'],company['name'],Jsonb(company)))


def insert(conn, table, row):
    query=sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT(id) DO NOTHING').format(
        sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row))
    return conn.execute(query,list(row.values())).rowcount


def save_actual(conn,a):
    cid=company_id(a.company)
    count=insert(conn,'earnings_actuals',{'id':a.id,'company_id':cid,'content_hash':digest(a),
        'concept':a.concept,'period_start':a.start,'period_end':a.end,'value':a.value,
        'unit':a.unit,'basis':a.basis,'accession':a.accession,'filed_date':a.filed,'form':a.form,
        'fiscal_year':a.fiscal_year,'fiscal_period':a.fiscal_period,'source_url':a.source_url,
        'derivation':a.derivation,'payload':Jsonb(plain(a))})
    for i,parent in enumerate(a.parents):
        conn.execute('INSERT INTO earnings_actual_edges(child_id,parent_id,company_id,position) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',(a.id,parent,cid,i))
    return count


def save_guidance(conn,g):
    return insert(conn,'guidance_versions',{'id':g.id,'company_id':company_id(g.company),'content_hash':digest(g),
        'issued_start':g.issued.start,'issued_end':g.issued.end,'issued_precision':g.issued.precision,
        'filed_date':g.filed,'period_start':g.start,'period_end':g.end,'metric':g.metric,'low':g.low,'high':g.high,
        'currency':g.unit,'basis':g.basis,'status':g.status,'accession':g.accession,'exhibit':g.exhibit,
        'source_url':g.source_url,'quote':g.quote,'original_verified':g.original_verified,'payload':Jsonb(plain(g))})


def save_calculation(conn,r):
    cid=company_id(r.company)
    insert(conn,'hurdle_calculations',{'id':r.id,'company_id':cid,'as_of':r.as_of,
        'formula_version':r.formula_version,'policy_version':r.policy.version,'policy':Jsonb(plain(r.policy)),
        'state':r.state,'reason_codes':list(r.codes),'remaining_low':r.remaining_low,'remaining_high':r.remaining_high,
        'growth_low':r.growth_low,'growth_high':r.growth_high,'payload':Jsonb(plain(r))})
    for role,identifier in r.inputs.items():
        conn.execute('''INSERT INTO hurdle_input_edges(calculation_id,company_id,role,actual_id,guidance_id)
            VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
            (r.id,cid,role,None if role=='guidance' else identifier,identifier if role=='guidance' else None))


def save_outcome(conn,r,annual):
    insert(conn,'guidance_outcomes',{'id':r['id'],'company_id':company_id(r['company']),'as_of':r['as_of'],
        'actual_id':annual.id,'original_guidance_id':r['original_guidance'],'latest_guidance_id':r['latest_guidance'],
        'result_issued_start':r['result_issued'].start,'result_issued_end':r['result_issued'].end,
        'result_issued_precision':r['result_issued'].precision,'filed_date':annual.filed,
        'result_accession':r['result_source']['accession'],'source_url':r['result_source']['url'],
        'original_class':r['original'],'latest_class':r['latest'],
        'original_subsequently_withdrawn':r['original_subsequently_withdrawn'],'payload':Jsonb(plain(r))})


def actual_from(row):
    d=dict(row)
    for k in ('start','end','filed'):d[k]=date.fromisoformat(d[k])
    d['value']=Decimal(d['value']);d['parents']=tuple(d['parents'])
    return Actual(**d)


def guidance_from(row):
    d=dict(row)
    d['issued']=DateInterval.read(d['issued'])
    for k in ('start','end','filed'):d[k]=date.fromisoformat(d[k])
    return Guidance(**d)


def records(conn,ticker):
    cid=company_id(ticker)
    a=[actual_from(r[0]) for r in conn.execute('SELECT payload FROM earnings_actuals WHERE company_id=%s AND derivation IS NULL',(cid,))]
    g=[guidance_from(r[0]) for r in conn.execute('SELECT payload FROM guidance_versions WHERE company_id=%s',(cid,))]
    return a,g


def calculation_from(row):
    d=dict(row);d['as_of']=date.fromisoformat(d['as_of']);d['policy']=Policy(**d['policy'])
    for k in ('remaining_low','remaining_high','growth_low','growth_high'):
        d[k]=Decimal(d[k]) if d[k] is not None else None
    d['codes']=tuple(d['codes']);d['details']=tuple(d['details'])
    return Calculation(**d)


def save_quarter_calculation(conn, result, prior=None):
    if prior is not None:
        if prior.id != result.inputs.get('prior_quarter'):
            raise ValueError('Quarter comparison identity mismatch')
        save_actual(conn, prior)
    return insert(conn, 'earnings_quarter_calculations', {
        'id': result.id, 'company_id': company_id(result.company), 'as_of': result.as_of,
        'period_start': result.target['start'], 'period_end': result.target['end'],
        'formula_version': result.formula_version, 'policy': Jsonb(plain(result.policy)),
        'guidance_id': result.inputs.get('guidance'), 'prior_quarter_id': result.inputs.get('prior_quarter'),
        'state': result.state, 'reason_codes': list(result.codes),
        'guidance_low': result.guidance_low, 'guidance_high': result.guidance_high,
        'growth_low': result.growth_low, 'growth_high': result.growth_high,
        'payload': Jsonb(plain(result))})


def save_quarter_outcome(conn, result):
    return insert(conn, 'earnings_quarter_outcomes', {
        'id': result['id'], 'company_id': company_id(result['company']), 'as_of': result['as_of'],
        'period_start': result['period_start'], 'period_end': result['period_end'],
        'guidance_id': result['guidance'], 'actual_id': result['actual'],
        'classification': result['classification'], 'reason_codes': result['codes'],
        'result_issued_start': result['result_issued'].start,
        'result_issued_end': result['result_issued'].end,
        'result_filed_date': result['result_source']['filed_date'],
        'result_accession': result['result_source']['accession'],
        'result_source_url': result['result_source']['url'], 'payload': Jsonb(plain(result))})


def quarter_calculation_from(row):
    from .quarters import QuarterCalculation
    d=dict(row); d['as_of']=date.fromisoformat(d['as_of']);d['policy']=Policy(**d['policy'])
    for k in ('guidance_low','guidance_high','growth_low','growth_high'):
        d[k]=Decimal(d[k]) if d[k] is not None else None
    d['codes']=tuple(d['codes']);d['details']=tuple(d['details'])
    return QuarterCalculation(**d)
