import type { CompanySummary } from './types';
export function filterCompanies(companies: CompanySummary[], query: string): CompanySummary[] {
  const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return companies.filter(c => words.every(w => `${c.ticker} ${c.name}`.toLocaleLowerCase().includes(w)));
}
export function normalizedTicker(value: string): string | null {
  const ticker = value.trim().toUpperCase();
  return /^[A-Z][A-Z0-9.-]{0,9}$/.test(ticker) ? ticker : null;
}
export function validAsOf(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0,10) === value;
}
