export type Source = { id: string; concept: string; start: string; end: string; filed: string; value: string; unit: string; basis: string; accession: string; source_url: string; parents?: string[] };
export type Metric = { key: string; label: string; value: string | null; display: string; unit: string; basis: string; state: string; reason: string | null; formula: string | null; sources: Source[] };
export type CompanySummary = { ticker: string; name: string; cik: string; as_of: string | null; hurdle_state?: string | null; forecast_status?: string | null; verdict?: string | null };
export type Guide = { id: string; low: string | null; high: string | null; issued: { start: string; end: string; precision: string }; filed: string; start: string; end: string; status: string; original_verified: boolean; range_display: string; source_url: string; accession: string; exhibit: string; quote: string; change: { low: string; high: string } | null };
export type CompanyReport = {
  id: string; as_of: string; report_version: string;
  company: { ticker: string; name: string; cik: string; fiscal_label: string; period_start: string; period_end: string; basis: string; calendar: string };
  latest_actual_release?: {ytd_end:string;filed_date:string;issued_date:string;source_url:string;accession:string;period_quote:string} | null;
  overview: { type: string; start: string | null; end: string | null; filed: string | null; age_days: number | null; stale: boolean; metrics: Metric[] }[];
  guidance: Guide[]; guidance_review_through: string;
  hurdle: { id: string; state: string; codes: string[]; details: string[]; inputs: Record<string, string>; formula_version: string };
  hurdle_display: Record<string, string>;
  forecast: { id: string; method: string; status: string; verdict: string | null; codes: string[]; details: string[]; interval_reason: string; assumptions: string[] };
  forecast_display: Record<string, string>;
  selected_inputs: Record<string, Source>;
  evaluation: { status: string; sample_size: number; covered_companies: number; coverage_denominator: number; classification_samples: number; classification_correct: number; limitations: string[]; missing_companies: string[]; cases: { company: string; forecast_date: string; status: string; reason: string | null; case: { scope_notes: string; scope_sources: { url: string; filed_date: string }[] } }[] };
  evaluation_display: Record<string, string>;
  changes: { previous_report_id: string | null; causes: string[]; input_versions: Record<string, {before: string | null; after: string | null}> };
  reporting: { next_report: {type: string; date?: string | null; status: string; expected_window?: { start: string; end: string }; source_url?: string; source_date?: string }; annual_result: { type: string; status: string; expected_window?: {start: string; end: string} } };
  coverage_notes: string[];
};

export type PublicCompanyReport = Omit<CompanyReport, 'forecast' | 'forecast_display' | 'evaluation' | 'evaluation_display'> & Partial<Pick<CompanyReport, 'forecast' | 'forecast_display' | 'evaluation' | 'evaluation_display'>> & {quarterly?: QuarterView | null};
export type QuarterView = {
  company:string; as_of:string; formula_version:string; codes:string[]; details:string[];
  target:{label:string;start:string;end:string;prior_start:string;prior_end:string};
  inputs:Record<string,string>;
  guidance: {id?:string;low:string|null;high:string|null;issued:{start:string;end:string};filed:string;accession:string;exhibit:string;quote:string;source_url:string} | null;
  comparison:Source|null;
  display:{low:string|null;high:string|null;growth_low:string|null;growth_high:string|null;prior:string|null};
};
