import type { Deal, EventRow, ProposalRow } from "./types";
import { computeDealSummary } from "./dealSummary";
import { buyerType, type BuyerType } from "./labels";

export interface DealStatsRow {
  slug: string;
  dealName: string;
  target: string;
  acquirer: string;
  buyerType: BuyerType;
  firstBidPriceLow: number | null;
  firstBidPriceHigh: number | null;
  finalBidPrice: number | null;
  pctChange: number | null;
  pctChangeBasis: "low" | "high" | null;
  nRounds: number;
  nBidders: number;
  nCounteroffers: number;
  daysFirstContactToSigning: number | null;
  marketCheck: "yes" | "no" | "unknown";
  finalPremiumPct: number | null;
  hasActivist: boolean;
  bidStatsUnreviewed: boolean;
  timelineUnreviewed: boolean;
  marketCheckUnreviewed: boolean;
  activistUnreviewed: boolean;
  // Fact ids to link each cell to its evidence on the deal page
  // (/deals/[slug]?fact=<id> opens that fact's drawer directly).
  firstBidFactId: string | null;
  finalBidFactId: string | null;
  signingFactId: string | null;
  marketCheckFactId: string | null;
  activistFactId: string | null;
}

// One row per deal that actually has events/proposals from its latest
// (locked) run -- a deal with no completed extraction contributes
// nothing here, same convention listDealsSummary already uses for "not
// extracted" deals on the home page.
export function computeDealStatsRow(deal: Deal, events: EventRow[], proposals: ProposalRow[]): DealStatsRow | null {
  if (events.length === 0 && proposals.length === 0) return null;
  const s = computeDealSummary(events, proposals, deal.target);
  return {
    slug: deal.slug,
    dealName: deal.deal_name,
    target: deal.target,
    acquirer: deal.acquirer,
    buyerType: buyerType(deal.slug, deal.acquirer),
    firstBidPriceLow: s.firstBidPriceLow,
    firstBidPriceHigh: s.firstBidPriceHigh,
    finalBidPrice: s.finalBidPrice,
    pctChange: s.pctChange,
    pctChangeBasis: s.pctChangeBasis,
    nRounds: s.nRounds,
    nBidders: s.nBidders,
    nCounteroffers: s.nCounteroffers,
    daysFirstContactToSigning: s.daysFirstContactToSigning,
    marketCheck: s.marketCheck,
    finalPremiumPct: s.finalPremiumPct,
    hasActivist: s.hasActivist,
    bidStatsUnreviewed: s.bidStatsUnreviewed,
    timelineUnreviewed: s.timelineUnreviewed,
    marketCheckUnreviewed: s.marketCheckUnreviewed,
    activistUnreviewed: s.activistUnreviewed,
    firstBidFactId: s.firstBidProposal?.id ?? null,
    finalBidFactId: s.finalBidProposal?.id ?? null,
    signingFactId: s.signingEvent?.id ?? null,
    marketCheckFactId: s.marketCheckEvent?.id ?? null,
    activistFactId: s.firstActivistEvent?.id ?? null,
  };
}

export function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

export function mean(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

export interface GroupStats {
  n: number;
  medianPctChange: number | null;
  meanPctChange: number | null;
  medianRounds: number | null;
  medianDaysToSigning: number | null;
}

function groupStats(rows: DealStatsRow[]): GroupStats {
  return {
    n: rows.length,
    medianPctChange: median(rows.map((r) => r.pctChange).filter((v): v is number => v !== null)),
    meanPctChange: mean(rows.map((r) => r.pctChange).filter((v): v is number => v !== null)),
    medianRounds: median(rows.map((r) => r.nRounds)),
    medianDaysToSigning: median(
      rows.map((r) => r.daysFirstContactToSigning).filter((v): v is number => v !== null)
    ),
  };
}

export interface CrossDealSummary {
  nDeals: number;
  overall: GroupStats;
  byBuyerType: Record<BuyerType, GroupStats>;
}

// n is reported at every level (overall and per buyer-type split) since
// each is an independently small sample -- a reader comparing the
// strategic vs. sponsor medians needs to see how few deals each rests
// on, not just the pipeline's total deal count.
export function computeCrossDealSummary(rows: DealStatsRow[]): CrossDealSummary {
  const byType: Record<BuyerType, DealStatsRow[]> = { strategic: [], sponsor: [], unknown: [] };
  for (const row of rows) byType[row.buyerType].push(row);

  return {
    nDeals: rows.length,
    overall: groupStats(rows),
    byBuyerType: {
      strategic: groupStats(byType.strategic),
      sponsor: groupStats(byType.sponsor),
      unknown: groupStats(byType.unknown),
    },
  };
}
