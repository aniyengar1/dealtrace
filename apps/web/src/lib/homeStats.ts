import "server-only";

import { query } from "./db";
import { getHeadlineStats } from "./headlineStats";

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
  medianDaysFirstProposalToSigning: HomeStat | null;
  pctFirstBidderWon: HomeStat | null;
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

// Medians/n come straight from headline_stats -- the pipeline's own
// computation, already verified in this round to match this app's
// prior from-scratch TS port exactly. The one thing headline_stats
// doesn't carry is the per-deal pct_bump values a histogram needs to
// bucket, so those come from deal_metrics directly (same canonical
// cash-deal population pct_increase_cash_deals summarizes -- a non-null
// pct_bump with no exclusion reason).
export async function computeHomeStats(): Promise<HomeStats> {
  const [stats, pctBumpRows, canonicalCount] = await Promise.all([
    getHeadlineStats(),
    query<{ pct_bump: number }>(
      `SELECT pct_bump FROM deal_metrics WHERE is_canonical AND pct_bump IS NOT NULL AND pct_bump_exclusion_reason IS NULL`
    ),
    query<{ count: number }>(`SELECT count(*)::int AS count FROM deals WHERE is_canonical`),
  ]);

  const bidders = stats.bidders_who_submitted_a_proposal;
  const proposals = stats.proposals_per_deal;
  const pctBump = stats.pct_increase_cash_deals;
  const daysProposalToSigning = stats.days_first_proposal_to_signing;
  const firstBidderWon = stats.pct_first_bidder_is_eventual_acquirer;

  return {
    nDealsCovered: canonicalCount[0]?.count ?? 0,
    medianBidders: bidders?.median != null ? { value: bidders.median, n: bidders.n } : null,
    medianProposals: proposals?.median != null ? { value: proposals.median, n: proposals.n } : null,
    medianPctBump: pctBump?.median != null ? { value: pctBump.median, n: pctBump.n } : null,
    medianDaysFirstProposalToSigning:
      daysProposalToSigning?.median != null
        ? { value: daysProposalToSigning.median, n: daysProposalToSigning.n }
        : null,
    pctFirstBidderWon: firstBidderWon?.median != null ? { value: firstBidderWon.median, n: firstBidderWon.n } : null,
    pctBumpHistogram: buildHistogram(pctBumpRows.map((r) => r.pct_bump)),
  };
}
