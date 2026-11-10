import "server-only";

import { query, queryOne } from "./db";
import type {
  Deal,
  DealSummary,
  EventRow,
  ExtractionRun,
  Fact,
  ParagraphRow,
  ProposalRow,
  ValuationRow,
} from "./types";

export async function listDealsSummary(): Promise<DealSummary[]> {
  return query<DealSummary>(`
    WITH latest_run AS (
      SELECT DISTINCT ON (deal_id) id AS run_id, deal_id
      FROM extraction_runs
      ORDER BY deal_id, started_at DESC
    ),
    fact_counts AS (
      SELECT run_id, count(*) AS total, count(*) FILTER (WHERE review_status != 'unreviewed') AS reviewed
      FROM (
        SELECT run_id, review_status FROM events
        UNION ALL
        SELECT run_id, review_status FROM proposals
        UNION ALL
        SELECT run_id, review_status FROM valuations
      ) f
      GROUP BY run_id
    ),
    proposal_counts AS (
      SELECT run_id, count(*) AS n_proposals FROM proposals GROUP BY run_id
    ),
    final_proposal AS (
      SELECT DISTINCT ON (run_id) run_id, price_low, price_high
      FROM proposals
      ORDER BY run_id, (status = 'accepted') DESC, date_resolved DESC NULLS LAST
    ),
    signing AS (
      SELECT DISTINCT ON (run_id) run_id, date_start
      FROM events
      WHERE event_type = 'signing' AND date_start IS NOT NULL
      ORDER BY run_id, date_start DESC
    )
    SELECT
      d.id, d.slug, d.deal_name, d.target, d.acquirer, d.search_term,
      fprop.price_low AS final_price_low,
      fprop.price_high AS final_price_high,
      s.date_start AS signing_date,
      coalesce(pc.n_proposals, 0) AS n_proposals,
      coalesce(fc.total, 0) AS n_facts_total,
      coalesce(fc.reviewed, 0) AS n_facts_reviewed
    FROM deals d
    LEFT JOIN latest_run lr ON lr.deal_id = d.id
    LEFT JOIN fact_counts fc ON fc.run_id = lr.run_id
    LEFT JOIN proposal_counts pc ON pc.run_id = lr.run_id
    LEFT JOIN final_proposal fprop ON fprop.run_id = lr.run_id
    LEFT JOIN signing s ON s.run_id = lr.run_id
    ORDER BY d.deal_name
  `);
}

export async function getDealBySlug(slug: string): Promise<Deal | null> {
  return queryOne<Deal>(`SELECT id, slug, deal_name, target, acquirer, search_term FROM deals WHERE slug = $1`, [
    slug,
  ]);
}

export async function getLatestRunForDeal(dealId: string): Promise<ExtractionRun | null> {
  return queryOne<ExtractionRun>(
    `SELECT id, deal_id, run_dir, model, prompt_version, started_at
     FROM extraction_runs WHERE deal_id = $1 ORDER BY started_at DESC LIMIT 1`,
    [dealId]
  );
}

export async function getEventsForRun(runId: string): Promise<EventRow[]> {
  const rows = await query<Omit<EventRow, "record_type">>(
    `SELECT id, run_id, date_text, date_start, date_end, date_precision, event_type,
            parties, summary, source_paragraph_ids, source_quotes, passed,
            failure_reasons, review_status, reviewer_note
     FROM events WHERE run_id = $1 ORDER BY date_start NULLS LAST, date_text`,
    [runId]
  );
  return rows.map((r) => ({ record_type: "Event" as const, ...r }));
}

export async function getProposalsForRun(runId: string): Promise<ProposalRow[]> {
  const rows = await query<Omit<ProposalRow, "record_type">>(
    `SELECT id, run_id, date_text, date_resolved, proposer, recipient, price_low,
            price_high, premium_pct, currency, consideration_type, proposal_kind,
            status, source_paragraph_ids, source_quotes, passed, failure_reasons,
            review_status, reviewer_note
     FROM proposals WHERE run_id = $1 ORDER BY date_resolved NULLS LAST, date_text`,
    [runId]
  );
  return rows.map((r) => ({ record_type: "Proposal" as const, ...r }));
}

export async function getValuationsForRun(runId: string): Promise<ValuationRow[]> {
  const rows = await query<Omit<ValuationRow, "record_type">>(
    `SELECT id, run_id, advisor, method, metric, multiple_low, multiple_high,
            implied_price_low, implied_price_high, key_assumptions,
            source_paragraph_ids, source_quotes, passed, failure_reasons,
            review_status, reviewer_note
     FROM valuations WHERE run_id = $1 ORDER BY advisor, method`,
    [runId]
  );
  return rows.map((r) => ({ record_type: "ValuationAnalysis" as const, ...r }));
}

export async function getAllFactsForRun(runId: string): Promise<Fact[]> {
  const [events, proposals, valuations] = await Promise.all([
    getEventsForRun(runId),
    getProposalsForRun(runId),
    getValuationsForRun(runId),
  ]);
  return [...events, ...proposals, ...valuations];
}

export async function getParagraphsForDeal(dealId: string): Promise<Record<string, ParagraphRow>> {
  const rows = await query<ParagraphRow>(
    `SELECT paragraph_id, section_key, text FROM paragraphs WHERE deal_id = $1`,
    [dealId]
  );
  const byId: Record<string, ParagraphRow> = {};
  for (const row of rows) byId[row.paragraph_id] = row;
  return byId;
}
