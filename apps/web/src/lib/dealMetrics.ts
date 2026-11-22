import "server-only";

import { query, queryOne } from "./db";
import { type PriceBucket, type SortKey, type SortDir } from "./dealLabels";

export type { PriceBucket, SortKey, SortDir };

// Everything cross-deal (the Deal Explorer, /stats, the ticker) now
// reads from deal_metrics -- a table the pipeline computes once per
// bulk-load run (src/compute_deal_metrics.py) instead of this app
// re-deriving bidder counts, bump %, and days-to-signing per deal on
// every request. The only two columns a reader still needs that
// deal_metrics doesn't carry are signing_date and consideration_type
// (deal_metrics is a single summary row; those live on the specific
// signing event / final proposal), so those come from a lateral
// subquery each -- verified at 121ms for the full 964-row canonical
// set, well under this app's 500ms budget.
export interface DealMetricsRow {
  dealId: string;
  slug: string;
  dealName: string;
  isCanonical: boolean;
  targetDisplay: string;
  acquirerDisplay: string;
  nPartiesContacted: number;
  nBidders: number;
  nProposals: number;
  firstPrice: number | null;
  finalPrice: number | null;
  // True when finalPrice is a stock-exchange ratio ("0.36" meaning
  // 0.36 shares of the acquirer per target share), not a dollar
  // amount -- consideration_type alone can't tell these apart, since
  // an all-stock deal's final price is often a genuine stated dollar
  // figure too ("implied value of $X per share"). See
  // src.bulk_stats.compute_final_price_is_ratio_for_deal. Always use
  // this (via PriceValue) rather than checking considerationType
  // directly for display purposes.
  finalPriceIsRatio: boolean | null;
  pctBump: number | null;
  pctBumpExclusionReason: string | null;
  // Experimental -- read for completeness but never rendered or sorted
  // on; a round-3 spot-check found first-contact dates the least
  // reliable extracted field (5 of 9 field errors). Use
  // daysFirstProposalToSigning instead for anything user-facing.
  daysFirstContactToSigning: number | null;
  daysFirstProposalToSigning: number | null;
  firstBidderWon: boolean | null;
  pricePlausible: boolean | null;
  signingDate: string | null;
  considerationType: string | null;
  // 'proposals_not_extracted' for a genuine (non-excluded) sale process
  // whose extraction produced zero Proposal records at all (Twitter/
  // Musk, New Relic) -- null otherwise. Still shown on the site; only
  // affects whether its bidder/proposal/bump figures look misleadingly
  // like "0" instead of "unknown." See src.bulk_stats._proposals_not_extracted.
  dataQualityFlag: string | null;
  // Read deterministically from the filing's own text (src/deal_size.py),
  // never computed/inferred -- null for a curated deal (no cached
  // full-text HTML) or any filing that doesn't state the fact outright.
  sharesOutstanding: number | null;
  sharesOutstandingQuote: string | null;
  // Only ~14 of 821 filings state their own deal's aggregate value
  // outright; most don't, and this is null for them rather than an
  // estimate. Never an enterprise value -- see extract_aggregate_value's
  // own docstring for why that phrasing is deliberately excluded.
  aggregateValue: number | null;
  aggregateValueQuote: string | null;
}

interface DealMetricsDbRow {
  deal_id: string;
  slug: string;
  deal_name: string;
  is_canonical: boolean;
  target_display: string;
  acquirer_display: string;
  n_parties_contacted: number;
  n_bidders: number;
  n_proposals: number;
  first_price: number | null;
  final_price: number | null;
  final_price_is_ratio: boolean | null;
  pct_bump: number | null;
  pct_bump_exclusion_reason: string | null;
  days_first_contact_to_signing: number | null;
  days_first_proposal_to_signing: number | null;
  first_bidder_won: boolean | null;
  price_plausible: boolean | null;
  signing_date: string | null;
  consideration_type: string | null;
  data_quality_flag: string | null;
  shares_outstanding: number | null;
  shares_outstanding_quote: string | null;
  aggregate_value: number | null;
  aggregate_value_quote: string | null;
}

function toRow(r: DealMetricsDbRow): DealMetricsRow {
  return {
    dealId: r.deal_id,
    slug: r.slug,
    dealName: r.deal_name,
    isCanonical: r.is_canonical,
    targetDisplay: r.target_display,
    acquirerDisplay: r.acquirer_display,
    nPartiesContacted: r.n_parties_contacted,
    nBidders: r.n_bidders,
    nProposals: r.n_proposals,
    firstPrice: r.first_price,
    finalPrice: r.final_price,
    finalPriceIsRatio: r.final_price_is_ratio,
    pctBump: r.pct_bump,
    pctBumpExclusionReason: r.pct_bump_exclusion_reason,
    daysFirstContactToSigning: r.days_first_contact_to_signing,
    daysFirstProposalToSigning: r.days_first_proposal_to_signing,
    firstBidderWon: r.first_bidder_won,
    pricePlausible: r.price_plausible,
    signingDate: r.signing_date,
    considerationType: r.consideration_type,
    dataQualityFlag: r.data_quality_flag,
    sharesOutstanding: r.shares_outstanding,
    sharesOutstandingQuote: r.shares_outstanding_quote,
    aggregateValue: r.aggregate_value,
    aggregateValueQuote: r.aggregate_value_quote,
  };
}

const BASE_SELECT = `
  SELECT
    dm.deal_id, d.slug, d.deal_name, dm.is_canonical, dm.target_display, dm.acquirer_display,
    dm.n_parties_contacted, dm.n_bidders, dm.n_proposals, dm.first_price, dm.final_price, dm.final_price_is_ratio,
    dm.pct_bump, dm.pct_bump_exclusion_reason, dm.days_first_contact_to_signing,
    dm.days_first_proposal_to_signing, dm.first_bidder_won, dm.price_plausible, dm.data_quality_flag,
    dm.shares_outstanding, dm.shares_outstanding_quote, dm.aggregate_value, dm.aggregate_value_quote,
    (SELECT e.date_start FROM events e JOIN extraction_runs r2 ON r2.id = e.run_id
     WHERE r2.deal_id = d.id AND e.event_type = 'signing' AND e.date_start IS NOT NULL
     ORDER BY e.date_start DESC LIMIT 1) AS signing_date,
    (SELECT p.consideration_type FROM proposals p JOIN extraction_runs r3 ON r3.id = p.run_id
     WHERE r3.deal_id = d.id AND p.date_resolved IS NOT NULL
     ORDER BY p.date_resolved DESC LIMIT 1) AS consideration_type
  FROM deal_metrics dm
  JOIN deals d ON d.id = dm.deal_id
`;

// A deal with no completed extraction run at all (Twitter/Musk, New
// Relic -- zero events AND zero proposals on every run, including no
// run whatsoever) has nothing to show beyond its bare deals-table row,
// so it's excluded from every public query the same way an
// excluded_from_stats deal is -- no recompute needed, since
// extraction_runs/events/proposals already reflect reality; this is
// purely a query-time check. Reused verbatim by every public query
// below (sitemap, ticker, home stats) that needs the same scope.
// References dm.deal_id (every caller already has a deal_metrics dm in
// scope), not d.id, so this drops into a query with or without a
// "deals d" join present.
export const HAS_COMPLETED_RUN_SQL = `
  EXISTS (
    SELECT 1 FROM extraction_runs r WHERE r.deal_id = dm.deal_id
      AND (EXISTS (SELECT 1 FROM events e WHERE e.run_id = r.id)
           OR EXISTS (SELECT 1 FROM proposals p WHERE p.run_id = r.id))
  )
`;

// Every public listing reads from here, so the scope is "included"
// deals -- canonical (deduplicated), not excluded_from_stats
// (src.classify_deal_type: spin-offs, affiliated-manager mergers, and
// buyer-side-filer deals), AND with a completed extraction run --
// never canonical alone. A deal like Viasat/Inmarsat (filer_is_acquirer)
// is canonical but must never appear in a public count, list, or
// search result; neither must one with nothing extracted yet.
export async function listCanonicalDealMetrics(): Promise<DealMetricsRow[]> {
  const rows = await query<DealMetricsDbRow>(
    `${BASE_SELECT} WHERE dm.is_canonical AND NOT dm.excluded_from_stats AND ${HAS_COMPLETED_RUN_SQL} ORDER BY dm.computed_at DESC`
  );
  return rows.map(toRow);
}

export async function getDealMetricsBySlug(slug: string): Promise<DealMetricsRow | null> {
  const row = await queryOne<DealMetricsDbRow>(`${BASE_SELECT} WHERE d.slug = $1`, [slug]);
  return row ? toRow(row) : null;
}

export function priceBucketOf(price: number | null): PriceBucket {
  if (price === null) return "unknown";
  if (price < 20) return "under-20";
  if (price < 50) return "20-50";
  if (price < 100) return "50-100";
  return "over-100";
}

export interface DealsFilter {
  q?: string;
  year?: string;
  considerationType?: string;
  priceBucket?: PriceBucket;
  sort?: SortKey;
  dir?: SortDir;
  page?: number;
}

const PAGE_SIZE = 25;

// Filter + sort only, no pagination -- shared by filterAndSortDeals
// (the /deals table, 25 rows at a time) and the CSV export route
// (the whole filtered set, same filters/sort as whatever the reader
// was looking at).
export function filterAndSort(rows: DealMetricsRow[], filter: Omit<DealsFilter, "page">): DealMetricsRow[] {
  let filtered = rows;

  if (filter.q) {
    const q = filter.q.toLowerCase();
    filtered = filtered.filter(
      (r) => r.targetDisplay.toLowerCase().includes(q) || r.acquirerDisplay.toLowerCase().includes(q)
    );
  }
  if (filter.year) {
    filtered = filtered.filter((r) => r.signingDate?.startsWith(filter.year!));
  }
  if (filter.considerationType) {
    filtered = filtered.filter((r) => (r.considerationType ?? "unknown") === filter.considerationType);
  }
  if (filter.priceBucket) {
    filtered = filtered.filter((r) => priceBucketOf(r.finalPrice) === filter.priceBucket);
  }

  const sortKey = filter.sort ?? "nProposals";
  const dir = filter.dir === "asc" ? 1 : -1;
  const valueOf = (r: DealMetricsRow): number | null => {
    switch (sortKey) {
      case "signingDate":
        return r.signingDate ? Date.parse(r.signingDate) : null;
      case "finalPrice":
        return r.finalPrice;
      case "nBidders":
        return r.nBidders;
      case "nProposals":
        return r.nProposals;
      case "pctChange":
        return r.pctBump;
    }
  };
  // Signing date (most recent first) breaks ties on the primary sort --
  // most visible on the default "most proposals" sort, where dozens of
  // deals share a small integer proposal count and would otherwise fall
  // back to whatever order the query happened to return them in.
  const byRecentSigningDate = (a: DealMetricsRow, b: DealMetricsRow): number => {
    const ad = a.signingDate ? Date.parse(a.signingDate) : null;
    const bd = b.signingDate ? Date.parse(b.signingDate) : null;
    if (ad === null && bd === null) return 0;
    if (ad === null) return 1;
    if (bd === null) return -1;
    return bd - ad;
  };
  return [...filtered].sort((a, b) => {
    const av = valueOf(a);
    const bv = valueOf(b);
    if (av === null && bv === null) return byRecentSigningDate(a, b);
    if (av === null) return 1;
    if (bv === null) return -1;
    if (av === bv) return byRecentSigningDate(a, b);
    return (av - bv) * dir;
  });
}

export function filterAndSortDeals(rows: DealMetricsRow[], filter: DealsFilter) {
  const sorted = filterAndSort(rows, filter);
  const page = Math.max(1, filter.page ?? 1);
  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageRows = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return { rows: pageRows, total, page: Math.min(page, totalPages), totalPages, pageSize: PAGE_SIZE };
}

// Years actually present in the canonical signing-date lateral above --
// never a hardcoded range, so a filter option never promises a year
// that turns out to have zero matching deals.
export function availableYears(rows: DealMetricsRow[]): string[] {
  const years = new Set<string>();
  for (const r of rows) {
    if (r.signingDate) years.add(r.signingDate.slice(0, 4));
  }
  return Array.from(years).sort((a, b) => Number(b) - Number(a));
}

export interface LatestAddedDeal {
  slug: string;
  targetDisplay: string;
  acquirerDisplay: string;
  signingDate: string | null;
}

// A handful of bulk-extracted display names are entity-resolution
// artifacts, not real names -- a bare ticker-style fragment ("Dti",
// "Mitt", "Rep") rather than the company it stands for. Real company
// names, even short ones, are vanishingly rare at 4 letters or fewer
// once ampersands/periods/spaces are stripped ("H.I.G." being a known
// exception), so this is a cheap, good-enough filter for a single
// hero-line pick -- not a data-quality claim about the row itself,
// which still renders normally everywhere else on the site.
function looksTickerLike(name: string): boolean {
  return name.replace(/[^A-Za-z]/g, "").length <= 4;
}

const CANDIDATE_POOL_SIZE = 20;

// Most recently *signed* among included deals -- not most recently
// added to the dataset (deal_metrics.computed_at), since a bulk-load
// run can backfill a deal signed years ago and "latest deal added"
// reads better as "the newest real deal" than as a pipeline-internals
// timestamp. Pulls a small pool (not just the single top row) because
// the single newest signing can belong to a deal whose acquirer name
// didn't resolve to a real string.
export async function getLatestAddedDeal(): Promise<LatestAddedDeal | null> {
  const rows = await query<{ slug: string; target_display: string; acquirer_display: string; signing_date: string | null }>(
    `${BASE_SELECT} WHERE dm.is_canonical AND NOT dm.excluded_from_stats AND ${HAS_COMPLETED_RUN_SQL}
     ORDER BY signing_date DESC NULLS LAST LIMIT ${CANDIDATE_POOL_SIZE}`
  );
  const row = rows.find((r) => !looksTickerLike(r.target_display) && !looksTickerLike(r.acquirer_display));
  return row
    ? { slug: row.slug, targetDisplay: row.target_display, acquirerDisplay: row.acquirer_display, signingDate: row.signing_date }
    : null;
}
