import "server-only";

import { computeCanonicalStats } from "./canonicalStats";

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
  // both tails -- a handful of per-deal outliers are expected even
  // after bulk_stats.py's own sanity thresholds; a bounded bucket
  // absorbs them instead of a chart with one bar towering over the rest.
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

// Every number here is canonical-deals-only (deals.is_canonical), using
// the exact definitions and exclusion thresholds src/bulk_stats.py uses
// for data/output/stats/headline_stats.json -- see canonicalStats.ts
// for why this is computed here rather than read from that file.
export async function computeHomeStats(): Promise<HomeStats> {
  const canon = await computeCanonicalStats();

  return {
    nDealsCovered: canon.nCanonicalDeals,
    medianBidders: canon.medianBidders,
    medianProposals: canon.medianProposals,
    medianPctBump: canon.medianPctIncreaseCash,
    medianDaysToSigning: canon.medianDaysToSigning,
    pctBumpHistogram: buildHistogram(canon.pctIncreaseCashValues),
  };
}
