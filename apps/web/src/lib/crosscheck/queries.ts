import 'server-only';
import { query, queryOne } from '@/lib/db';
import { normalizedTicker } from './identity';
import type { CompanySummary, CompanyReport, PublicCompanyReport, QuarterView } from './types';

import { experimentalAnnualForecastEnabled, publicReport } from './features';

// JSON financial values are Decimal strings. Never select NUMERIC through the
// deals module's global float parser; all financial math remains in Python.
export async function listCompanies(): Promise<CompanySummary[]> {
  const rows=await query<CompanySummary>(`SELECT c.ticker,c.name,c.cik,r.payload->>'as_of' AS as_of,
    r.payload->'hurdle'->>'state' AS hurdle_state,r.payload->'forecast'->>'status' AS forecast_status,r.payload->'forecast'->>'verdict' AS verdict
    FROM companies c LEFT JOIN LATERAL (SELECT payload FROM earnings_company_reports
      WHERE company_id=c.id AND as_of<=CURRENT_DATE ORDER BY as_of DESC,created_at DESC,id DESC LIMIT 1) r ON true ORDER BY c.ticker`);
  if(experimentalAnnualForecastEnabled()) return rows;
  return rows.map(({forecast_status:_status,verdict:_verdict,...company})=>{void _status;void _verdict;return company;});
}
export async function companyData(value: string, asOf?: string): Promise<{company: CompanySummary; report: PublicCompanyReport | null; dates: string[]} | null> {
  const ticker=normalizedTicker(value);
  if (!ticker) return null;
  const company=await queryOne<CompanySummary>('SELECT ticker,name,cik FROM companies WHERE ticker=$1',[ticker]);
  if (!company) return null;
  const report=await queryOne<{payload: CompanyReport}>(`SELECT r.payload FROM earnings_company_reports r JOIN companies c ON c.id=r.company_id
    WHERE c.ticker=$1 AND ${asOf ? 'r.as_of=$2::date' : 'r.as_of<=CURRENT_DATE'} ORDER BY r.as_of DESC,r.created_at DESC,r.id DESC LIMIT 1`,asOf ? [ticker,asOf] : [ticker]);
  const dates=await query<{as_of: string}>(`SELECT DISTINCT r.as_of::text AS as_of FROM earnings_company_reports r JOIN companies c ON c.id=r.company_id WHERE c.ticker=$1 ORDER BY as_of DESC`,[ticker]);
  let visible:PublicCompanyReport|null=null;
  if(report) {
    visible=publicReport(report.payload);
    const quarter=await queryOne<{payload:QuarterView}>(`SELECT q.payload || jsonb_build_object(
      'guidance',g.payload || jsonb_build_object('id',g.id),'comparison',a.payload || jsonb_build_object('id',a.id),'display',jsonb_build_object(
        'low',to_char(g.low/1000000,'FM999999999990.000'),
        'high',to_char(g.high/1000000,'FM999999999990.000'),
        'growth_low',to_char(q.growth_low*100,'FM999999999990.00') || '%',
        'growth_high',to_char(q.growth_high*100,'FM999999999990.00') || '%',
        'prior',to_char(a.value/1000000,'FM999999999990.000'))) AS payload
      FROM earnings_quarter_calculations q JOIN companies c ON c.id=q.company_id
      LEFT JOIN guidance_versions g ON g.id=q.guidance_id
      LEFT JOIN earnings_actuals a ON a.id=q.prior_quarter_id
      WHERE c.ticker=$1 AND q.as_of=$2::date AND q.period_start>=$3::date AND q.period_end<=$4::date
      ORDER BY q.period_end DESC,q.created_at DESC,q.id DESC LIMIT 1`,
      [ticker,report.payload.as_of,report.payload.company.period_start,report.payload.company.period_end]);
    visible={...visible,quarterly:quarter?.payload??null};
  }
  return {company,report:visible,dates:dates.map(d=>d.as_of)};
}
