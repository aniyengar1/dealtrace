import "server-only";

import { listDeals, getLatestFactsRunForDeal, getEventsForRun, getProposalsForRun } from "./queries";
import { computeDealStatsRow, type DealStatsRow } from "./crossDealStats";
import { type PriceBucket, type SortKey, type SortDir } from "./dealLabels";

export type { PriceBucket, SortKey, SortDir };

// Every deal with a completed (locked) extraction run, each with its
// full derived stats row -- the same per-deal computation the stats
// page already does, reused here instead of re-deriving bidder counts,
// rounds, and bump % a second way. The pg pool (default max 10
// connections) naturally throttles concurrent requests, so Promise.all
// across however many hundred deals exist is safe, just queued.
export async function listAllDealStatsRows(): Promise<DealStatsRow[]> {
  const deals = await listDeals();
  const rows = await Promise.all(
    deals.map(async (deal) => {
      const run = await getLatestFactsRunForDeal(deal.id);
      if (!run) return null;
      const [events, proposals] = await Promise.all([getEventsForRun(run.id), getProposalsForRun(run.id)]);
      return computeDealStatsRow(deal, events, proposals);
    })
  );
  return rows.filter((r): r is DealStatsRow => r !== null);
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

export function filterAndSortDeals(rows: DealStatsRow[], filter: DealsFilter) {
  let filtered = rows;

  if (filter.q) {
    const q = filter.q.toLowerCase();
    filtered = filtered.filter(
      (r) => r.target.toLowerCase().includes(q) || r.acquirer.toLowerCase().includes(q)
    );
  }
  if (filter.year) {
    filtered = filtered.filter((r) => r.signingDate?.startsWith(filter.year!));
  }
  if (filter.considerationType) {
    filtered = filtered.filter((r) => (r.considerationType ?? "unknown") === filter.considerationType);
  }
  if (filter.priceBucket) {
    filtered = filtered.filter((r) => priceBucketOf(r.finalBidPrice) === filter.priceBucket);
  }

  const sortKey = filter.sort ?? "signingDate";
  const dir = filter.dir === "asc" ? 1 : -1;
  const valueOf = (r: DealStatsRow): number | null => {
    switch (sortKey) {
      case "signingDate":
        return r.signingDate ? Date.parse(r.signingDate) : null;
      case "finalPrice":
        return r.finalBidPrice;
      case "nBidders":
        return r.nBidders;
      case "nProposals":
        return r.nProposals;
      case "pctChange":
        return r.pctChange;
      case "daysToSigning":
        return r.daysFirstContactToSigning;
    }
  };
  const sorted = [...filtered].sort((a, b) => {
    const av = valueOf(a);
    const bv = valueOf(b);
    if (av === null && bv === null) return 0;
    if (av === null) return 1;
    if (bv === null) return -1;
    return (av - bv) * dir;
  });

  const page = Math.max(1, filter.page ?? 1);
  const total = sorted.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageRows = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return { rows: pageRows, total, page: Math.min(page, totalPages), totalPages, pageSize: PAGE_SIZE };
}

export function availableYears(rows: DealStatsRow[]): string[] {
  const years = new Set<string>();
  for (const r of rows) {
    if (r.signingDate) years.add(r.signingDate.slice(0, 4));
  }
  return Array.from(years).sort((a, b) => Number(b) - Number(a));
}
