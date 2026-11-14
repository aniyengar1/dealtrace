import "server-only";

import { listDeals, getLatestFactsRunForDeal, getEventsForRun, getProposalsForRun } from "./queries";
import { computeDealStatsRow, median, type DealStatsRow } from "./crossDealStats";

export interface HomeStat {
  value: number;
  n: number;
}

export interface PctBumpBucket {
  label: string;
  count: number;
}

export interface HomeStats {
  nDealsCovered: number;
  medianBidders: HomeStat | null;
  medianProposals: HomeStat | null;
  medianPctBump: HomeStat | null;
  medianDaysToSigning: HomeStat | null;
  // Histogram of first-proposal -> final-price % change, open-ended on
  // both tails -- with hundreds of deals (and extractions that haven't
  // been through review yet), a handful of per-deal outliers are
  // expected; a bounded bucket absorbs them instead of a chart with one
  // bar a thousand times taller than the rest.
  pctBumpHistogram: PctBumpBucket[];
}

const PCT_BUMP_BUCKETS: { label: string; min: number; max: number }[] = [
  { label: "< -25%", min: -Infinity, max: -25 },
  { label: "-25 to 0%", min: -25, max: 0 },
  { label: "0 to 25%", min: 0, max: 25 },
  { label: "25 to 50%", min: 25, max: 50 },
  { label: "50 to 100%", min: 50, max: 100 },
  { label: "> 100%", min: 100, max: Infinity },
];

function buildHistogram(values: number[]): PctBumpBucket[] {
  return PCT_BUMP_BUCKETS.map(({ label, min, max }) => ({
    label,
    count: values.filter((v) => v >= min && v < max).length,
  }));
}

// Every deal with a completed (locked) extraction run -- the same
// "latest facts run" each deal page and the stats page already key off
// of, so the home page never shows a number that page wouldn't back up.
// Fetched concurrently (not one deal at a time) -- with 1000+ deals now
// in the bulk-loaded table, a sequential per-deal loop was the actual
// bottleneck on the home page, not the hero video.
async function loadDealStatsRows(): Promise<DealStatsRow[]> {
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

function stat(values: number[]): HomeStat | null {
  const m = median(values);
  return m === null ? null : { value: m, n: values.length };
}

export async function computeHomeStats(): Promise<HomeStats> {
  const rows = await loadDealStatsRows();
  const pctBumps = rows.map((r) => r.pctChange).filter((v): v is number => v !== null);

  return {
    nDealsCovered: rows.length,
    medianBidders: stat(rows.map((r) => r.nBidders)),
    medianProposals: stat(rows.map((r) => r.nProposals)),
    medianPctBump: stat(pctBumps),
    medianDaysToSigning: stat(
      rows.map((r) => r.daysFirstContactToSigning).filter((v): v is number => v !== null)
    ),
    pctBumpHistogram: buildHistogram(pctBumps),
  };
}
