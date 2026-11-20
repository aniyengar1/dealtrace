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

// "Latest run" is per (deal, section), not per deal -- a deal can have
// its background section re-extracted (events/proposals) under a newer
// prompt version while its opinion sections (valuations) are still only
// covered by an older run; each half should independently use whichever
// run actually covered it most recently, not go blank just because a
// *different* section got a newer run.
export async function listDealsSummary(): Promise<DealSummary[]> {
  return query<DealSummary>(`
    WITH latest_facts_run AS (
      SELECT DISTINCT ON (r.deal_id) r.id AS run_id, r.deal_id
      FROM extraction_runs r
      WHERE EXISTS (SELECT 1 FROM events e WHERE e.run_id = r.id)
         OR EXISTS (SELECT 1 FROM proposals p WHERE p.run_id = r.id)
      ORDER BY r.deal_id, r.started_at DESC
    ),
    latest_valuations_run AS (
      SELECT DISTINCT ON (r.deal_id) r.id AS run_id, r.deal_id
      FROM extraction_runs r
      WHERE EXISTS (SELECT 1 FROM valuations v WHERE v.run_id = r.id)
      ORDER BY r.deal_id, r.started_at DESC
    ),
    fact_counts AS (
      SELECT run_id, count(*) AS total, count(*) FILTER (WHERE review_status != 'unreviewed') AS reviewed
      FROM (
        SELECT run_id, review_status FROM events
        UNION ALL
        SELECT run_id, review_status FROM proposals
      ) f
      GROUP BY run_id
    ),
    valuation_counts AS (
      SELECT run_id, count(*) AS total, count(*) FILTER (WHERE review_status != 'unreviewed') AS reviewed
      FROM valuations
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
      d.id, d.slug, d.deal_name, d.target, d.acquirer, d.search_term, d.is_canonical,
      fprop.price_low AS final_price_low,
      fprop.price_high AS final_price_high,
      s.date_start AS signing_date,
      coalesce(pc.n_proposals, 0) AS n_proposals,
      coalesce(fc.total, 0) + coalesce(vc.total, 0) AS n_facts_total,
      coalesce(fc.reviewed, 0) + coalesce(vc.reviewed, 0) AS n_facts_reviewed
    FROM deals d
    LEFT JOIN latest_facts_run lfr ON lfr.deal_id = d.id
    LEFT JOIN latest_valuations_run lvr ON lvr.deal_id = d.id
    LEFT JOIN fact_counts fc ON fc.run_id = lfr.run_id
    LEFT JOIN valuation_counts vc ON vc.run_id = lvr.run_id
    LEFT JOIN proposal_counts pc ON pc.run_id = lfr.run_id
    LEFT JOIN final_proposal fprop ON fprop.run_id = lfr.run_id
    LEFT JOIN signing s ON s.run_id = lfr.run_id
    ORDER BY (coalesce(fc.total, 0) + coalesce(vc.total, 0) = 0) ASC, s.date_start DESC NULLS LAST, d.deal_name ASC
  `);
}

export async function listDeals(): Promise<Deal[]> {
  return query<Deal>(`SELECT id, slug, deal_name, target, acquirer, search_term FROM deals ORDER BY deal_name`);
}

export async function getDealBySlug(slug: string): Promise<Deal | null> {
  return queryOne<Deal>(
    `SELECT id, slug, deal_name, target, acquirer, search_term, is_canonical, duplicate_of
     FROM deals WHERE slug = $1`,
    [slug]
  );
}

// Whole-table index of just the columns proxy.ts needs to decide
// exists/redirect/pass-through for every deal slug in one query -- small
// enough (one row per deal, four scalar columns) to load in full and
// cache in memory rather than re-querying per request.
export async function listDealSlugIndex(): Promise<
  { id: string; slug: string; is_canonical: boolean; duplicate_of: string | null }[]
> {
  return query(`SELECT id, slug, is_canonical, duplicate_of FROM deals`);
}

// The most recent run that actually extracted events/proposals (the
// background section) for this deal -- never a run that only covered
// opinion sections, even if it happens to be newer.
export async function getLatestFactsRunForDeal(dealId: string): Promise<ExtractionRun | null> {
  return queryOne<ExtractionRun>(
    `SELECT r.id, r.deal_id, r.run_dir, r.model, r.prompt_version, r.started_at
     FROM extraction_runs r
     WHERE r.deal_id = $1
       AND (EXISTS (SELECT 1 FROM events e WHERE e.run_id = r.id)
            OR EXISTS (SELECT 1 FROM proposals p WHERE p.run_id = r.id))
     ORDER BY r.started_at DESC LIMIT 1`,
    [dealId]
  );
}

// The most recent run that actually extracted valuations (the opinion
// sections) for this deal -- independent of whichever run is latest for
// facts, so a background-only re-extraction never blanks out valuations
// that an earlier, still-only run already covered.
export async function getLatestValuationsRunForDeal(dealId: string): Promise<ExtractionRun | null> {
  return queryOne<ExtractionRun>(
    `SELECT r.id, r.deal_id, r.run_dir, r.model, r.prompt_version, r.started_at
     FROM extraction_runs r
     WHERE r.deal_id = $1
       AND EXISTS (SELECT 1 FROM valuations v WHERE v.run_id = r.id)
     ORDER BY r.started_at DESC LIMIT 1`,
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

// Events/proposals from the deal's latest facts run, valuations from its
// latest valuations run -- the two can legitimately be different runs
// (see listDealsSummary's comment above).
export async function getAllFactsForDeal(dealId: string): Promise<Fact[]> {
  const [factsRun, valuationsRun] = await Promise.all([
    getLatestFactsRunForDeal(dealId),
    getLatestValuationsRunForDeal(dealId),
  ]);
  const [events, proposals, valuations] = await Promise.all([
    factsRun ? getEventsForRun(factsRun.id) : Promise.resolve([]),
    factsRun ? getProposalsForRun(factsRun.id) : Promise.resolve([]),
    valuationsRun ? getValuationsForRun(valuationsRun.id) : Promise.resolve([]),
  ]);
  return [...events, ...proposals, ...valuations];
}

// Best-effort link from a deal to the SEC filing it was extracted from --
// "deals" has no filing reference of its own (it's hand-registered in
// src/run.py's DEALS dict, independent of the automated discovery table),
// so this joins on the discovery table's own fuzzy name match instead.
// Null (hidden, never guessed) when no confident match exists.
export async function getFilingUrlForDeal(searchTerm: string): Promise<string | null> {
  const row = await queryOne<{ primary_file_name: string }>(
    `SELECT primary_file_name FROM deal_candidates
     WHERE target_name ILIKE '%' || $1 || '%'
       AND classification = 'public_company_acquisition'
     ORDER BY primary_filed_date DESC
     LIMIT 1`,
    [searchTerm]
  );
  return row ? `https://www.sec.gov/Archives/${row.primary_file_name}` : null;
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
