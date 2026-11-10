export type DatePrecision = "day" | "month" | "range" | "unknown";
export type ReviewStatus = "unreviewed" | "confirmed" | "rejected";

export interface Deal {
  id: string;
  slug: string;
  deal_name: string;
  target: string;
  acquirer: string;
  search_term: string;
}

export interface ExtractionRun {
  id: string;
  deal_id: string;
  run_dir: string;
  model: string;
  prompt_version: string;
  started_at: string;
}

export interface EventRow {
  record_type: "Event";
  id: string;
  run_id: string;
  date_text: string;
  date_start: string | null;
  date_end: string | null;
  date_precision: DatePrecision;
  event_type: string;
  parties: string[];
  summary: string;
  source_paragraph_ids: string[];
  source_quotes: string[];
  passed: boolean;
  failure_reasons: string[];
  review_status: ReviewStatus;
  reviewer_note: string | null;
}

export interface ProposalRow {
  record_type: "Proposal";
  id: string;
  run_id: string;
  date_text: string;
  date_resolved: string | null;
  proposer: string;
  recipient: string;
  price_low: number | null;
  price_high: number | null;
  premium_pct: number | null;
  currency: string | null;
  consideration_type: string;
  proposal_kind: string;
  status: string;
  source_paragraph_ids: string[];
  source_quotes: string[];
  passed: boolean;
  failure_reasons: string[];
  review_status: ReviewStatus;
  reviewer_note: string | null;
}

export interface ValuationRow {
  record_type: "ValuationAnalysis";
  id: string;
  run_id: string;
  advisor: string;
  method: string;
  metric: string;
  multiple_low: number | null;
  multiple_high: number | null;
  implied_price_low: number | null;
  implied_price_high: number | null;
  key_assumptions: string[];
  source_paragraph_ids: string[];
  source_quotes: string[];
  passed: boolean;
  failure_reasons: string[];
  review_status: ReviewStatus;
  reviewer_note: string | null;
}

export type Fact = EventRow | ProposalRow | ValuationRow;
export type FactType = Fact["record_type"];

export interface ParagraphRow {
  paragraph_id: string;
  section_key: string;
  text: string;
}

export interface DealSummary extends Deal {
  final_price_low: number | null;
  final_price_high: number | null;
  signing_date: string | null;
  n_proposals: number;
  n_facts_total: number;
  n_facts_reviewed: number;
}
