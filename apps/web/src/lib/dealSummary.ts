import type { EventRow, ProposalRow } from "./types";
import { parseFilingDate } from "./format";
import { computeRounds } from "./rounds";

export interface DealSummaryStats {
  firstBidPrice: number | null;
  finalBidPrice: number | null;
  pctChange: number | null;
  nRounds: number;
  nBidders: number;
  daysFirstContactToSigning: number | null;
  marketCheck: "yes" | "no" | "unknown";
  nConfirmed: number;
  nUnreviewed: number;
  nRejectedExcluded: number;
}

// Rejected facts are known-wrong, so they're excluded from every figure
// below; confirmed and unreviewed facts are both included (unreviewed
// isn't known-wrong, just unverified yet) -- nConfirmed/nUnreviewed/
// nRejectedExcluded say exactly how much of this summary rests on each,
// so a reader can judge how much to trust it before it's fully reviewed.
export function computeDealSummary(
  events: EventRow[],
  proposals: ProposalRow[],
  target: string
): DealSummaryStats {
  const includedEvents = events.filter((e) => e.review_status !== "rejected");
  const includedProposals = proposals.filter((p) => p.review_status !== "rejected");
  const nRejectedExcluded =
    events.length - includedEvents.length + (proposals.length - includedProposals.length);
  const nConfirmed =
    includedEvents.filter((e) => e.review_status === "confirmed").length +
    includedProposals.filter((p) => p.review_status === "confirmed").length;
  const nUnreviewed =
    includedEvents.filter((e) => e.review_status === "unreviewed").length +
    includedProposals.filter((p) => p.review_status === "unreviewed").length;

  const dated = includedProposals
    .map((p) => {
      const date = parseFilingDate(p.date_text, p.date_resolved);
      const price = p.price_high ?? p.price_low;
      return date && price !== null ? { proposal: p, date, price } : null;
    })
    .filter((d): d is { proposal: ProposalRow; date: Date; price: number } => d !== null)
    .sort((a, b) => a.date.getTime() - b.date.getTime());

  const firstBidPrice = dated[0]?.price ?? null;
  const accepted = dated.find((d) => d.proposal.status === "accepted");
  const finalEntry = accepted ?? dated[dated.length - 1] ?? null;
  const finalBidPrice = finalEntry?.price ?? null;
  const pctChange =
    firstBidPrice !== null && finalBidPrice !== null && firstBidPrice !== 0
      ? ((finalBidPrice - firstBidPrice) / firstBidPrice) * 100
      : null;

  const { rounds } = computeRounds(includedProposals, includedEvents);
  const nRounds = rounds.length;

  const nBidders = new Set(includedProposals.map((p) => p.proposer).filter((p) => p !== target)).size;

  const firstContact = includedEvents
    .filter((e) => e.event_type === "first_contact" && e.date_start)
    .sort((a, b) => (a.date_start! < b.date_start! ? -1 : 1))[0];
  const signing = includedEvents
    .filter((e) => e.event_type === "signing" && e.date_start)
    .sort((a, b) => (a.date_start! < b.date_start! ? 1 : -1))[0];

  let daysFirstContactToSigning: number | null = null;
  if (firstContact?.date_start && signing?.date_start) {
    const start = new Date(`${firstContact.date_start}T00:00:00Z`).getTime();
    const end = new Date(`${signing.date_start}T00:00:00Z`).getTime();
    daysFirstContactToSigning = Math.round((end - start) / (1000 * 60 * 60 * 24));
  }

  // Heuristic, not a direct extraction: 2+ distinct bidders is itself
  // strong evidence a market check happened, regardless of whether the
  // filing narrates it as one; with exactly one bidder, a
  // market_check_decision event existing at all means the board at
  // least considered and decided against (or quietly ran) a broader
  // process, otherwise there's no basis to say either way.
  const hasMarketCheckEvent = includedEvents.some((e) => e.event_type === "market_check_decision");
  let marketCheck: "yes" | "no" | "unknown";
  if (nBidders >= 2) marketCheck = "yes";
  else if (hasMarketCheckEvent) marketCheck = "no";
  else marketCheck = "unknown";

  return {
    firstBidPrice,
    finalBidPrice,
    pctChange,
    nRounds,
    nBidders,
    daysFirstContactToSigning,
    marketCheck,
    nConfirmed,
    nUnreviewed,
    nRejectedExcluded,
  };
}
