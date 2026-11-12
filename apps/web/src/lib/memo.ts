import type { Deal, EventRow, ProposalRow, ValuationRow } from "./types";
import { computeDealSummary, type DealSummaryStats } from "./dealSummary";
import { acquirerDisplayName, CORE_EVENT_TYPES, eventTypeLabel, proposalKindLabel, proposalStatusLabel, valuationMethodLabel } from "./labels";
import { formatEventDate, formatPrice, formatPriceRange, formatPct, parseFilingDate } from "./format";

// A single memo line: its text plus the fact it was read off, so every
// consumer (the on-page memo, the Markdown export) can cite it without
// re-deriving the lookup. factId/paragraphIds are both empty only for a
// synthesized absence-of-evidence statement ("no notable features
// identified") -- there's no paragraph to point to for something the
// filing simply doesn't mention.
export interface MemoLine {
  text: string;
  factId: string | null;
  paragraphIds: string[];
}

export interface BidHistoryRow {
  dateLabel: string;
  proposer: string;
  recipient: string;
  priceLabel: string;
  premiumLabel: string;
  kindLabel: string;
  statusLabel: string;
  factId: string;
  paragraphIds: string[];
}

// Where the deal's final price falls relative to this advisor's implied
// range -- "below range"/"above range" means the deal priced outside
// what this analysis implied, "within range" means it didn't.
export type ValuationVsFinal = "below range" | "within range" | "above range" | "final price not available";

export interface ValuationSummaryRow {
  advisor: string;
  methodLabel: string;
  impliedRangeLabel: string;
  vsFinal: ValuationVsFinal;
  factId: string;
  paragraphIds: string[];
}

export interface DealMemo {
  dealName: string;
  target: string;
  acquirer: string;
  dealTerms: MemoLine[];
  partiesAndAdvisors: MemoLine[];
  timeline: MemoLine[];
  bidHistory: BidHistoryRow[];
  valuationSummary: ValuationSummaryRow[];
  notableFeatures: MemoLine[];
  talkingPoints: MemoLine[];
}

const TERMINATION_FEE_RE = /termination fee/i;

function line(text: string, factId: string | null = null, paragraphIds: string[] = []): MemoLine {
  return { text, factId, paragraphIds };
}

function buildDealTerms(
  acquirerDisplay: string,
  events: EventRow[],
  summary: DealSummaryStats
): MemoLine[] {
  const lines: MemoLine[] = [];
  const final = summary.finalBidProposal;
  if (final) {
    lines.push(
      line(
        `Per-share consideration: ${formatPriceRange(final.price_low, final.price_high)} in ${final.consideration_type} from ${acquirerDisplay}.`,
        final.id,
        final.source_paragraph_ids
      )
    );
  } else {
    lines.push(line("Per-share consideration: not extracted."));
  }

  if (summary.finalPremiumPct !== null && final) {
    lines.push(line(`Premium: ${formatPct(summary.finalPremiumPct)} over the pre-announcement price.`, final.id, final.source_paragraph_ids));
  }

  const terminationFeeEvents = events.filter(
    (e) => TERMINATION_FEE_RE.test(e.summary) || e.source_quotes.some((q) => TERMINATION_FEE_RE.test(q))
  );
  if (terminationFeeEvents.length > 0) {
    for (const e of terminationFeeEvents) {
      lines.push(line(`Termination fee: ${e.summary}`, e.id, e.source_paragraph_ids));
    }
  } else {
    lines.push(line("Termination fee: not extracted."));
  }

  return lines;
}

function buildPartiesAndAdvisors(
  target: string,
  acquirerDisplay: string,
  events: EventRow[],
  valuations: ValuationRow[]
): MemoLine[] {
  const lines: MemoLine[] = [line(`Target: ${target}.`), line(`Acquirer: ${acquirerDisplay}.`)];

  const byAdvisor = new Map<string, ValuationRow[]>();
  for (const v of valuations) {
    const existing = byAdvisor.get(v.advisor) ?? [];
    existing.push(v);
    byAdvisor.set(v.advisor, existing);
  }
  for (const [advisor, rows] of byAdvisor) {
    const methods = Array.from(new Set(rows.map((r) => valuationMethodLabel(r.method)))).join(", ");
    lines.push(line(`Financial advisor: ${advisor} (${methods}).`, rows[0].id, rows[0].source_paragraph_ids));
  }

  const excluded = new Set([target.toLowerCase(), acquirerDisplay.toLowerCase()]);
  const seen = new Set<string>();
  for (const e of events) {
    for (const party of e.parties) {
      const key = party.toLowerCase();
      if (excluded.has(key) || seen.has(key)) continue;
      seen.add(key);
      lines.push(line(`Named party: ${party}.`, e.id, e.source_paragraph_ids));
    }
  }

  return lines;
}

function buildTimeline(events: EventRow[]): MemoLine[] {
  return events
    .filter((e) => CORE_EVENT_TYPES.has(e.event_type))
    .filter((e) => e.date_start !== null)
    .sort((a, b) => (a.date_start! < b.date_start! ? -1 : a.date_start! > b.date_start! ? 1 : 0))
    .map((e) => line(`${formatEventDate(e)} — ${eventTypeLabel(e.event_type)}: ${e.summary}`, e.id, e.source_paragraph_ids));
}

function buildBidHistory(proposals: ProposalRow[]): BidHistoryRow[] {
  return [...proposals]
    .map((p) => ({ p, date: parseFilingDate(p.date_text, p.date_resolved) }))
    .sort((a, b) => {
      if (a.date === null && b.date === null) return 0;
      if (a.date === null) return 1;
      if (b.date === null) return -1;
      return a.date.getTime() - b.date.getTime();
    })
    .map(({ p }) => ({
      dateLabel: p.date_text,
      proposer: p.proposer,
      recipient: p.recipient,
      priceLabel: formatPriceRange(p.price_low, p.price_high),
      premiumLabel: formatPct(p.premium_pct),
      kindLabel: proposalKindLabel(p.proposal_kind),
      statusLabel: proposalStatusLabel(p.status),
      factId: p.id,
      paragraphIds: p.source_paragraph_ids,
    }));
}

function buildValuationSummary(valuations: ValuationRow[], finalBidPrice: number | null): ValuationSummaryRow[] {
  return valuations.map((v) => {
    let vsFinal: ValuationVsFinal = "final price not available";
    if (finalBidPrice !== null && v.implied_price_low !== null && v.implied_price_high !== null) {
      if (finalBidPrice < v.implied_price_low) vsFinal = "below range";
      else if (finalBidPrice > v.implied_price_high) vsFinal = "above range";
      else vsFinal = "within range";
    }
    return {
      advisor: v.advisor,
      methodLabel: valuationMethodLabel(v.method),
      impliedRangeLabel: formatPriceRange(v.implied_price_low, v.implied_price_high),
      vsFinal,
      factId: v.id,
      paragraphIds: v.source_paragraph_ids,
    };
  });
}

function buildNotableFeatures(events: EventRow[], summary: DealSummaryStats): MemoLine[] {
  const lines: MemoLine[] = [];
  for (const e of events.filter((e) => e.event_type === "withdrawal")) {
    lines.push(line(`Withdrawal: ${e.summary}`, e.id, e.source_paragraph_ids));
  }
  for (const e of events.filter((e) => e.event_type === "re_engagement")) {
    lines.push(line(`Re-engagement: ${e.summary}`, e.id, e.source_paragraph_ids));
  }
  for (const e of events.filter((e) => e.event_type === "activist")) {
    lines.push(line(`Activist activity: ${e.summary}`, e.id, e.source_paragraph_ids));
  }
  if (summary.marketCheck === "no" && summary.marketCheckEvent) {
    lines.push(
      line(`No market check: ${summary.marketCheckEvent.summary}`, summary.marketCheckEvent.id, summary.marketCheckEvent.source_paragraph_ids)
    );
  }
  if (lines.length === 0) {
    lines.push(line("No withdrawals, re-engagements, activist activity, or market-check decision identified in the extracted facts."));
  }
  return lines;
}

function buildTalkingPoints(acquirerDisplay: string, target: string, summary: DealSummaryStats): MemoLine[] {
  const candidates: MemoLine[] = [];

  if (summary.pctChange !== null && summary.firstBidProposal && summary.finalBidProposal) {
    const sign = summary.pctChange >= 0 ? "+" : "";
    const firstLabel = formatPriceRange(summary.firstBidPriceLow, summary.firstBidPriceHigh);
    const finalLabel = formatPrice(summary.finalBidPrice);
    const days = summary.daysFirstBidToFinalBid;
    candidates.push(
      line(
        `${acquirerDisplay} raised its bid ${sign}${summary.pctChange.toFixed(1)}% from ${firstLabel} to ${finalLabel} across ${summary.nBidderBids} bid(s)${days !== null ? ` in ${days} day(s)` : ""}.`,
        summary.finalBidProposal.id,
        [...summary.firstBidProposal.source_paragraph_ids, ...summary.finalBidProposal.source_paragraph_ids]
      )
    );
  }

  if (summary.nBidders > 0 && summary.daysFirstContactToSigning !== null && summary.firstContactEvent && summary.signingEvent) {
    candidates.push(
      line(
        `${summary.nBidders} bidder(s) competed over ${summary.nRounds} round(s); the process ran ${summary.daysFirstContactToSigning} day(s) from first contact to signing.`,
        summary.signingEvent.id,
        [...summary.firstContactEvent.source_paragraph_ids, ...summary.signingEvent.source_paragraph_ids]
      )
    );
  }

  if (summary.nCounteroffers > 0 && summary.counterofferProposals.length > 0) {
    const first = summary.counterofferProposals[0];
    candidates.push(
      line(
        `${target}'s board countered ${summary.nCounteroffers} time(s) before reaching agreement.`,
        first.id,
        summary.counterofferProposals.flatMap((p) => p.source_paragraph_ids)
      )
    );
  }

  if (summary.marketCheck === "no" && summary.marketCheckEvent) {
    candidates.push(
      line("No formal market check was conducted before signing.", summary.marketCheckEvent.id, summary.marketCheckEvent.source_paragraph_ids)
    );
  } else if (summary.hasActivist && summary.firstActivistEvent) {
    candidates.push(
      line("An activist shareholder campaign preceded or accompanied the process.", summary.firstActivistEvent.id, summary.firstActivistEvent.source_paragraph_ids)
    );
  } else if (summary.marketCheck === "yes") {
    candidates.push(
      line(`A market check involving ${summary.nBidders} bidders preceded signing.`, summary.finalBidProposal?.id ?? null, summary.finalBidProposal?.source_paragraph_ids ?? [])
    );
  }

  if (summary.finalPremiumPct !== null && summary.finalBidProposal) {
    candidates.push(
      line(`The accepted bid represented a stated premium of ${formatPct(summary.finalPremiumPct)}.`, summary.finalBidProposal.id, summary.finalBidProposal.source_paragraph_ids)
    );
  }

  return candidates.slice(0, 4);
}

export function buildDealMemo(
  deal: Deal,
  events: EventRow[],
  proposals: ProposalRow[],
  valuations: ValuationRow[]
): DealMemo {
  const acquirerDisplay = acquirerDisplayName(deal.slug, deal.acquirer);
  const summary = computeDealSummary(events, proposals, deal.target);
  const includedEvents = events.filter((e) => e.review_status !== "rejected");
  const includedProposals = proposals.filter((p) => p.review_status !== "rejected");

  return {
    dealName: deal.deal_name,
    target: deal.target,
    acquirer: acquirerDisplay,
    dealTerms: buildDealTerms(acquirerDisplay, includedEvents, summary),
    partiesAndAdvisors: buildPartiesAndAdvisors(deal.target, acquirerDisplay, includedEvents, valuations),
    timeline: buildTimeline(includedEvents),
    bidHistory: buildBidHistory(includedProposals),
    valuationSummary: buildValuationSummary(valuations, summary.finalBidPrice),
    notableFeatures: buildNotableFeatures(includedEvents, summary),
    talkingPoints: buildTalkingPoints(acquirerDisplay, deal.target, summary),
  };
}

function citationSuffix(paragraphIds: string[]): string {
  if (paragraphIds.length === 0) return "";
  return ` (${paragraphIds.map((id) => `¶${id}`).join(", ")})`;
}

export function renderMemoMarkdown(memo: DealMemo): string {
  const out: string[] = [];
  out.push(`# ${memo.dealName} — Deal Memo`, "");
  out.push(`${memo.target} → ${memo.acquirer}`, "");

  out.push("## Deal terms", "");
  for (const l of memo.dealTerms) out.push(`- ${l.text}${citationSuffix(l.paragraphIds)}`);
  out.push("");

  out.push("## Parties and advisors", "");
  for (const l of memo.partiesAndAdvisors) out.push(`- ${l.text}${citationSuffix(l.paragraphIds)}`);
  out.push("");

  out.push("## Process timeline", "");
  for (const l of memo.timeline) out.push(`- ${l.text}${citationSuffix(l.paragraphIds)}`);
  out.push("");

  out.push("## Bid history", "");
  out.push("| Date | Proposer | Recipient | Price | Premium | Kind | Status | Source |");
  out.push("| --- | --- | --- | --- | --- | --- | --- | --- |");
  for (const r of memo.bidHistory) {
    out.push(
      `| ${r.dateLabel} | ${r.proposer} | ${r.recipient} | ${r.priceLabel} | ${r.premiumLabel} | ${r.kindLabel} | ${r.statusLabel} | ${r.paragraphIds.map((id) => `¶${id}`).join(", ")} |`
    );
  }
  out.push("");

  out.push("## Valuation summary", "");
  out.push("| Advisor | Method | Implied range | vs. final price | Source |");
  out.push("| --- | --- | --- | --- | --- |");
  for (const r of memo.valuationSummary) {
    out.push(`| ${r.advisor} | ${r.methodLabel} | ${r.impliedRangeLabel} | ${r.vsFinal} | ${r.paragraphIds.map((id) => `¶${id}`).join(", ")} |`);
  }
  out.push("");

  out.push("## Notable features", "");
  for (const l of memo.notableFeatures) out.push(`- ${l.text}${citationSuffix(l.paragraphIds)}`);
  out.push("");

  out.push("## Talking points", "");
  for (const l of memo.talkingPoints) out.push(`- ${l.text}${citationSuffix(l.paragraphIds)}`);
  out.push("");

  return out.join("\n");
}
