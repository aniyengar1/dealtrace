import type { EventRow, ProposalRow } from "./types";
import { parseFilingDate } from "./format";

export interface PlottableProposal {
  proposal: ProposalRow;
  date: Date;
}

export interface Round {
  proposals: PlottableProposal[];
}

export interface RoundBreak {
  events: EventRow[];
}

// "the target publicly ending the process" has no dedicated event_type --
// it shows up as an "announcement" (or occasionally a "rejection"/
// "withdrawal" event whose own text describes a formal public step, e.g.
// a press release) whose own text says so. Doesn't match an unrelated
// announcement (e.g. a different acquisition entirely, or the deal's own
// final signing announcement), since neither uses this language.
const PROCESS_END_RE =
  /standalone|terminat|conclu\w*\s+(its|the)?\s*(strategic )?review|completion of its strategic review|press release announcing its (rejection|withdrawal)/i;

// A proposal counts as "live" for its bidder unless it was explicitly
// withdrawn -- "rejected" means that specific number was declined, not
// that the bidder left (they routinely come back with a revised number
// days or months later with no separate "re-engagement" event marking
// it, since nothing about the relationship actually paused); only a
// self-initiated "withdrawn" (schemas.ProposalStatus: "the proposer
// pulled it") is a real exit signal.
function isLiveStatus(status: string): boolean {
  return status !== "withdrawn";
}

function paragraphOrderKey(ids: string[]): number {
  const first = ids[0];
  const match = first ? first.match(/(\d+)$/) : null;
  return match ? parseInt(match[1], 10) : Number.POSITIVE_INFINITY;
}

function sortByDateThenParagraph<T>(items: T[], dateOf: (t: T) => Date, idsOf: (t: T) => string[]): T[] {
  return [...items].sort((a, b) => {
    const diff = dateOf(a).getTime() - dateOf(b).getTime();
    if (diff !== 0) return diff;
    return paragraphOrderKey(idsOf(a)) - paragraphOrderKey(idsOf(b));
  });
}

// Same bidder/date/price proposals that differ only in status are near-
// certainly the same real proposal extracted twice from overlapping
// chunks, each chunk's call having seen a different amount of later
// context. Prefer whichever status is more "currently active" (open or
// accepted over superseded/rejected/withdrawn) since the open/accepted
// reading reflects the proposal's own contemporaneous state, which is
// what bidder-activity tracking needs -- the alternative, more
// "concluded"-sounding status usually just means a different chunk
// already knew how the story ended.
const STATUS_ACTIVITY_RANK: Record<string, number> = {
  accepted: 0,
  open: 1,
  superseded: 2,
  rejected: 3,
  withdrawn: 3,
};

function dedupeProposalsForActivity(proposals: ProposalRow[]): ProposalRow[] {
  const byKey = new Map<string, ProposalRow>();
  for (const p of proposals) {
    const key = `${p.proposer}|${p.date_resolved ?? p.date_text}|${p.price_low}|${p.price_high}`;
    const existing = byKey.get(key);
    if (!existing || (STATUS_ACTIVITY_RANK[p.status] ?? 9) < (STATUS_ACTIVITY_RANK[existing.status] ?? 9)) {
      byKey.set(key, p);
    }
  }
  return Array.from(byKey.values());
}

function parseEventDate(event: EventRow): Date | null {
  return event.date_start ? new Date(`${event.date_start}T00:00:00Z`) : null;
}

// Shared by the bid chart (one panel per round) and the deal summary box
// (round count) so the two can never disagree on where a round splits.
//
// A round ends only on a process-level break: (a) a withdrawal/rejection
// after which NO bidder has an active (open/accepted) proposal -- a
// consortium member leaving, or one of several bidders dropping out
// while others continue, is explicitly not a break; (b) the target
// publicly ending the process (a "standalone"/review-concluded
// announcement); or (c) a re-engagement event, which by construction
// only gets that event_type when it follows such a break. Each proposal
// is assigned to the round defined by however many of these break dates
// fall strictly before it -- "strictly before" (not "on or before") so
// a same-day reactive proposal (e.g. the target's own rejection,
// dated the same day as the bidder's withdrawal) stays in the round
// that's ending, not the one that hasn't started yet.
export function computeRounds(
  proposals: ProposalRow[],
  events: EventRow[],
  target: string
): { rounds: Round[]; breaks: RoundBreak[] } {
  const bidderProposals = dedupeProposalsForActivity(proposals.filter((p) => p.proposer !== target));
  const bidderDated = bidderProposals
    .map((p) => {
      const date = parseFilingDate(p.date_text, p.date_resolved);
      return date ? { p, date } : null;
    })
    .filter((x): x is { p: ProposalRow; date: Date } => x !== null);
  const sortedBidderProposals = sortByDateThenParagraph(
    bidderDated,
    (x) => x.date,
    (x) => x.p.source_paragraph_ids
  );

  function activeBidderCountAsOf(t: number): number {
    const latestStatus = new Map<string, string>();
    for (const { p, date } of sortedBidderProposals) {
      if (date.getTime() > t) break;
      latestStatus.set(p.proposer, p.status);
    }
    let count = 0;
    for (const status of latestStatus.values()) {
      if (isLiveStatus(status)) count++;
    }
    return count;
  }

  // Case (a): a withdrawal/rejection after which no bidder has a live
  // proposal -- the last one standing just left.
  const exitBreaks = events
    .map((event) => ({ event, date: parseEventDate(event) }))
    .filter((x): x is { event: EventRow; date: Date } => x.date !== null)
    .filter(({ event }) => event.event_type === "withdrawal" || event.event_type === "rejection")
    .filter(({ date }) => activeBidderCountAsOf(date.getTime()) === 0);

  // Case (b): the target publicly ends the process -- independent of
  // bidder-activity bookkeeping, since the target isn't a tracked bidder.
  const processEndBreaks = events
    .map((event) => ({ event, date: parseEventDate(event) }))
    .filter((x): x is { event: EventRow; date: Date } => x.date !== null)
    .filter(({ event }) => ["announcement", "rejection", "withdrawal"].includes(event.event_type))
    .filter(({ event }) => PROCESS_END_RE.test(event.summary));

  // Case (c): re-engagement after either of the above.
  const reEngagements = events
    .map((event) => ({ event, date: parseEventDate(event) }))
    .filter((x): x is { event: EventRow; date: Date } => x.date !== null)
    .filter(({ event }) => event.event_type === "re_engagement");

  const boundaryEvents = [...exitBreaks, ...processEndBreaks, ...reEngagements];

  // Closing boundaries (exit/process-end) and opening boundaries
  // (re-engagement) need opposite tie-breaking on their own date: a
  // same-day reactive proposal (e.g. the target's rejection, dated the
  // same day as the bidder's withdrawal) belongs to the round that's
  // ending, but a proposal dated the same day as a re-engagement belongs
  // to the round that's starting -- otherwise a re-engagement and its own
  // first proposal land on opposite sides of a split that shouldn't exist.
  const closeDates = Array.from(new Set([...exitBreaks, ...processEndBreaks].map((b) => b.date.getTime())));
  const openDates = Array.from(new Set(reEngagements.map((b) => b.date.getTime())));

  function roundIndexFor(t: number): number {
    const closed = closeDates.filter((d) => d < t).length;
    const opened = openDates.filter((d) => d <= t).length;
    return closed + opened;
  }

  const chartable = proposals
    .map((proposal) => {
      const date = parseFilingDate(proposal.date_text, proposal.date_resolved);
      return date ? { proposal, date } : null;
    })
    .filter((x): x is PlottableProposal => x !== null);
  const sortedChartable = sortByDateThenParagraph(
    chartable,
    (x) => x.date,
    (x) => x.proposal.source_paragraph_ids
  );

  const byRoundIndex = new Map<number, PlottableProposal[]>();
  for (const point of sortedChartable) {
    const roundIndex = roundIndexFor(point.date.getTime());
    const existing = byRoundIndex.get(roundIndex) ?? [];
    existing.push(point);
    byRoundIndex.set(roundIndex, existing);
  }

  const nonEmptyIndices = Array.from(byRoundIndex.keys()).sort((a, b) => a - b);
  const rounds: Round[] = nonEmptyIndices.map((i) => ({ proposals: byRoundIndex.get(i)! }));

  const breaks: RoundBreak[] = [];
  for (let i = 0; i < rounds.length - 1; i++) {
    const afterDate = rounds[i].proposals[rounds[i].proposals.length - 1].date.getTime();
    const beforeDate = rounds[i + 1].proposals[0].date.getTime();
    const eventsInGap = boundaryEvents
      .filter((b) => b.date.getTime() > afterDate && b.date.getTime() <= beforeDate)
      .map((b) => b.event);
    // De-duplicate by event_type -- repeated extraction of the same
    // narrative beat (e.g. two near-identical "Withdrawal" events from
    // overlapping chunks) should label the divider once, not twice.
    const seen = new Set<string>();
    const uniqueEvents = eventsInGap.filter((e) => {
      if (seen.has(e.event_type)) return false;
      seen.add(e.event_type);
      return true;
    });
    breaks.push({ events: uniqueEvents });
  }

  return { rounds, breaks };
}
