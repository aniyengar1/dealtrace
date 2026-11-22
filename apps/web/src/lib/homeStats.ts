import "server-only";

import { query } from "./db";
import { HAS_COMPLETED_RUN_SQL } from "./dealMetrics";
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
  minSigningYear: number | null;
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

export interface IncludedDealsSummary {
  count: number;
  minSigningYear: number | null;
}

// Shared by the home page (hero/stats-band counts, "since YYYY") and
// the root layout's <title>/description -- both need the same
// included-deal population (canonical AND not excluded_from_stats, see
// listCanonicalDealMetrics) and the same "since" floor, computed once
// here instead of drifting into two separately hand-maintained numbers.
export async function getIncludedDealsSummary(): Promise<IncludedDealsSummary> {
  // Per-deal signing year has to be derived the same way
  // dealMetrics.ts's BASE_SELECT derives signingDate -- the single
  // latest-dated "signing" event for that deal -- not a flat MIN/MAX
  // over every signing-typed event joined in. A background section can
  // legitimately contain more than one "signing" event (MoneyGram's
  // narrative mentions its 2017 agreement with Ant Financial, which
  // fell through, before the actual 2022 MDP signing this deal
  // tracks); averaging/MIN-ing across all of them pulled a stray 2017
  // into "since YYYY" even though every included deal's OWN latest
  // signing -- the figure the year filter and this stat both need to
  // agree on -- falls in 2020 or later.
  const rows = await query<{ count: number; min_year: number | null }>(
    `SELECT count(*)::int AS count, MIN(signing_year)::int AS min_year
     FROM (
       SELECT (
         SELECT EXTRACT(YEAR FROM e.date_start)::int
         FROM events e JOIN extraction_runs r ON r.id = e.run_id
         WHERE r.deal_id = dm.deal_id AND e.event_type = 'signing' AND e.date_start IS NOT NULL
         ORDER BY e.date_start DESC LIMIT 1
       ) AS signing_year
       FROM deal_metrics dm
       WHERE dm.is_canonical AND NOT dm.excluded_from_stats AND ${HAS_COMPLETED_RUN_SQL}
     ) sub`
  );
  return { count: rows[0]?.count ?? 0, minSigningYear: rows[0]?.min_year ?? null };
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
  const [stats, pctBumpRows, dealsSummary] = await Promise.all([
    getHeadlineStats(),
    query<{ pct_bump: number }>(
      `SELECT dm.pct_bump FROM deal_metrics dm
       WHERE dm.is_canonical AND NOT dm.excluded_from_stats
         AND dm.pct_bump IS NOT NULL AND dm.pct_bump_exclusion_reason IS NULL`
    ),
    getIncludedDealsSummary(),
  ]);

  const bidders = stats.bidders_who_submitted_a_proposal;
  const proposals = stats.proposals_per_deal;
  const pctBump = stats.pct_increase_cash_deals;
  const daysProposalToSigning = stats.days_first_proposal_to_signing;
  const firstBidderWon = stats.pct_first_bidder_is_eventual_acquirer;

  return {
    nDealsCovered: dealsSummary.count,
    minSigningYear: dealsSummary.minSigningYear,
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
