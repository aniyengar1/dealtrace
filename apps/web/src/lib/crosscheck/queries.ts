import 'server-only';
import { query, queryOne } from '@/lib/db';
import { normalizedTicker } from './identity';
import type { CompanySummary, CompanyReport } from './types';

// JSON financial values are Decimal strings. Never select NUMERIC through the
// deals module's global float parser; all financial math remains in Python.
export async function listCompanies(): Promise<CompanySummary[]> {
  return query<CompanySummary>(`SELECT c.ticker,c.name,c.cik,r.payload->>'as_of' AS as_of,
    r.payload->'forecast'->>'status' AS forecast_status,r.payload->'forecast'->>'verdict' AS verdict
    FROM companies c LEFT JOIN LATERAL (SELECT payload FROM earnings_company_reports
      WHERE company_id=c.id AND as_of<=CURRENT_DATE ORDER BY as_of DESC,created_at DESC,id DESC LIMIT 1) r ON true ORDER BY c.ticker`);
}
export async function companyData(value: string, asOf?: string): Promise<{company: CompanySummary; report: CompanyReport | null; dates: string[]} | null> {
  const ticker=normalizedTicker(value);
  if (!ticker) return null;
  const company=await queryOne<CompanySummary>('SELECT ticker,name,cik FROM companies WHERE ticker=$1',[ticker]);
  if (!company) return null;
  const report=await queryOne<{payload: CompanyReport}>(`SELECT r.payload FROM earnings_company_reports r JOIN companies c ON c.id=r.company_id
    WHERE c.ticker=$1 AND ${asOf ? 'r.as_of=$2::date' : 'r.as_of<=CURRENT_DATE'} ORDER BY r.as_of DESC,r.created_at DESC,r.id DESC LIMIT 1`,asOf ? [ticker,asOf] : [ticker]);
  const dates=await query<{as_of: string}>(`SELECT DISTINCT r.as_of::text AS as_of FROM earnings_company_reports r JOIN companies c ON c.id=r.company_id WHERE c.ticker=$1 ORDER BY as_of DESC`,[ticker]);
  return {company,report:report?.payload ?? null,dates:dates.map(d=>d.as_of)};
}
