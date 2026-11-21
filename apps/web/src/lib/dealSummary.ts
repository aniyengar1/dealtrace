import type { EventRow, ProposalRow } from "./types";
import { parseFilingDate } from "./format";
import { computeRounds } from "./rounds";

export interface DealSummaryStats {
  firstBidPriceLow: number | null;
  firstBidPriceHigh: number | null;
  finalBidPrice: number | null;
  pctChange: number | null;
  pctChangeBasis: "low" | "high" | null;
  nRounds: number;
  nBidders: number;
  nBidderBids: number;
  nCounteroffers: number;
  // Experimental -- not rendered anywhere; a round-3 spot-check found
  // first-contact dates the least reliable extracted field (5 of 9
  // field errors). Kept on the type for internal/future use only; use
  // daysFirstProposalToSigning for anything user-facing.
  daysFirstContactToSigning: number | null;
  daysFirstProposalToSigning: number | null;
  daysFirstBidToFinalBid: number | null;
  marketCheck: "yes" | "no" | "unknown";
  finalPremiumPct: number | null;
  hasActivist: boolean;
  nConfirmed: number;
  nUnreviewed: number;
  nRejectedExcluded: number;
  // Which stat groups above rest on at least one not-yet-reviewed fact --
  // not known-wrong (that's nRejectedExcluded), just not verified yet. A
  // consumer surfacing these numbers (the cross-deal stats page, the
  // memo) should mark them accordingly rather than present them with the
  // same confidence as a fully-reviewed figure.
  bidStatsUnreviewed: boolean; // first/final bid, % change, rounds, bidders, counteroffers, premium
  timelineUnreviewed: boolean; // days first contact -> signing
  marketCheckUnreviewed: boolean; // market check yes/no/unknown
  activistUnreviewed: boolean; // activist involvement
  // The specific fact each headline number was read off of, for anything
  // that consumes this summary and needs to cite or link to its evidence
  // (the cross-deal stats page, the memo) instead of recomputing the same
  // lookup a second time.
  firstBidProposal: ProposalRow | null;
  finalBidProposal: ProposalRow | null;
  firstContactEvent: EventRow | null;
  signingEvent: EventRow | null;
  marketCheckEvent: EventRow | null;
  firstActivistEvent: EventRow | null;
  counterofferProposals: ProposalRow[];
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

  const firstEntry = dated[0] ?? null;
  const firstBidPriceLow = firstEntry?.proposal.price_low ?? null;
  const firstBidPriceHigh = firstEntry?.proposal.price_high ?? null;
  // A range's upper end is the conventional one to quote against the
  // final price ("they opened at up to $X, settled at $Y"); only labeled
  // "low" when there's no high end to prefer.
  const pctChangeBasis: "low" | "high" | null =
    firstBidPriceHigh !== null ? "high" : firstBidPriceLow !== null ? "low" : null;
  const firstBidPriceForPct = pctChangeBasis === "high" ? firstBidPriceHigh : firstBidPriceLow;

  const accepted = dated.find((d) => d.proposal.status === "accepted");
  const finalEntry = accepted ?? dated[dated.length - 1] ?? null;
  const finalBidPrice = finalEntry?.price ?? null;
  const pctChange =
    firstBidPriceForPct !== null && finalBidPrice !== null && firstBidPriceForPct !== 0
      ? ((finalBidPrice - firstBidPriceForPct) / firstBidPriceForPct) * 100
      : null;
  const finalPremiumPct = finalEntry?.proposal.premium_pct ?? null;
  const daysFirstBidToFinalBid =
    firstEntry && finalEntry
      ? Math.round((finalEntry.date.getTime() - firstEntry.date.getTime()) / (1000 * 60 * 60 * 24))
      : null;

  const { rounds } = computeRounds(includedProposals, includedEvents, target);
  const nRounds = rounds.length;

  const bidderProposals = includedProposals.filter((p) => p.proposer !== target);
  const nBidders = new Set(bidderProposals.map((p) => p.proposer)).size;
  // "N bids" in a talking point reads as "{acquirer} raised its bid ...
  // across N bids" -- that's the WINNING bidder's own bid count, not
  // every competing bidder's combined (a multi-bidder auction with 3
  // other parties who each bid once and dropped out shouldn't inflate
  // this to "4 bids" when the eventual acquirer itself only revised
  // twice). Falls back to 0 if there's no final (price-bearing) entry to
  // anchor "the winning bidder" to.
  const winningBidder = finalEntry?.proposal.proposer ?? null;
  const nBidderBids = winningBidder !== null ? dated.filter((d) => d.proposal.proposer === winningBidder).length : 0;
  const counterofferProposals = includedProposals.filter((p) => p.proposer === target);
  const nCounteroffers = counterofferProposals.length;

  const activistEvents = includedEvents.filter((e) => e.event_type === "activist");
  const hasActivist = activistEvents.length > 0;

  const firstContact = includedEvents
    .filter((e) => e.event_type === "first_contact" && e.date_start)
    .sort((a, b) => (a.date_start! < b.date_start! ? -1 : 1))[0];
  const signing = includedEvents
    .filter((e) => e.event_type === "signing" && e.date_start)
    .sort((a, b) => (a.date_start! < b.date_start! ? 1 : -1))[0];

  // No first_contact event extracted (it happens) shouldn't blank this
  // figure out entirely -- the earliest dated fact of any kind is still
  // a reasonable lower bound for when the process began.
  let processStartDate: string | null = firstContact?.date_start ?? null;
  if (!processStartDate) {
    const allDates = [
      ...includedEvents.map((e) => e.date_start).filter((d): d is string => d !== null),
      ...dated.map((d) => d.date.toISOString().slice(0, 10)),
    ].sort();
    processStartDate = allDates[0] ?? null;
  }

  let daysFirstContactToSigning: number | null = null;
  if (processStartDate && signing?.date_start) {
    const start = new Date(`${processStartDate}T00:00:00Z`).getTime();
    const end = new Date(`${signing.date_start}T00:00:00Z`).getTime();
    daysFirstContactToSigning = Math.round((end - start) / (1000 * 60 * 60 * 24));
  }

  // The reliable, user-facing timeline figure -- anchored to the
  // earliest dated PROPOSAL rather than first contact (see
  // daysFirstContactToSigning's comment above).
  let daysFirstProposalToSigning: number | null = null;
  if (firstEntry && signing?.date_start) {
    const start = firstEntry.date.getTime();
    const end = new Date(`${signing.date_start}T00:00:00Z`).getTime();
    daysFirstProposalToSigning = Math.round((end - start) / (1000 * 60 * 60 * 24));
  }

  // Heuristic, not a direct extraction: 2+ distinct bidders is itself
  // strong evidence a market check happened, regardless of whether the
  // filing narrates it as one; with exactly one bidder, a
  // market_check_decision event existing at all means the board at
  // least considered and decided against (or quietly ran) a broader
  // process, otherwise there's no basis to say either way.
  const marketCheckEvent = includedEvents.find((e) => e.event_type === "market_check_decision");
  let marketCheck: "yes" | "no" | "unknown";
  if (nBidders >= 2) marketCheck = "yes";
  else if (marketCheckEvent) marketCheck = "no";
  else marketCheck = "unknown";

  const bidStatsUnreviewed = includedProposals.some((p) => p.review_status === "unreviewed");
  const timelineUnreviewed = [firstContact, signing].some((e) => e?.review_status === "unreviewed");
  const marketCheckUnreviewed =
    bidderProposals.some((p) => p.review_status === "unreviewed") ||
    marketCheckEvent?.review_status === "unreviewed";
  const activistUnreviewed = activistEvents.some((e) => e.review_status === "unreviewed");

  return {
    firstBidPriceLow,
    firstBidPriceHigh,
    finalBidPrice,
    pctChange,
    pctChangeBasis,
    nRounds,
    nBidders,
    nBidderBids,
    nCounteroffers,
    daysFirstContactToSigning,
    daysFirstProposalToSigning,
    daysFirstBidToFinalBid,
    marketCheck,
    finalPremiumPct,
    hasActivist,
    nConfirmed,
    nUnreviewed,
    nRejectedExcluded,
    bidStatsUnreviewed,
    timelineUnreviewed,
    marketCheckUnreviewed,
    activistUnreviewed,
    firstBidProposal: firstEntry?.proposal ?? null,
    finalBidProposal: finalEntry?.proposal ?? null,
    firstContactEvent: firstContact ?? null,
    signingEvent: signing ?? null,
    marketCheckEvent: marketCheckEvent ?? null,
    firstActivistEvent: activistEvents[0] ?? null,
    counterofferProposals,
  };
}
