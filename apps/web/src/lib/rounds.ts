import type { EventRow, ProposalRow } from "./types";
import { parseFilingDate } from "./format";

// schemas.EventType has no separate "termination" value -- withdrawal is
// the type used for a bidder (or the process) walking away, which is
// what "termination" means here too.
const ROUND_BREAK_EVENT_TYPES = new Set(["withdrawal", "re_engagement"]);
const GAP_DAYS_THRESHOLD = 90;

export interface PlottableProposal {
  proposal: ProposalRow;
  date: Date;
}

export interface Round {
  proposals: PlottableProposal[];
}

export interface RoundBreak {
  reason: "event" | "gap";
  events: EventRow[];
  gapDays: number;
}

function parseEventDate(event: EventRow): Date | null {
  return event.date_start ? new Date(`${event.date_start}T00:00:00Z`) : null;
}

// Shared by the bid chart (one panel per round) and the deal summary box
// (round count) so the two can never disagree on where a round splits.
// A round ends when a withdrawal/re-engagement event falls between two
// consecutive proposals, or when more than 90 days pass with no new
// proposal -- either signals the negotiation went cold and what follows
// is a materially separate round, not a continuous back-and-forth.
export function computeRounds(
  proposals: ProposalRow[],
  events: EventRow[]
): { rounds: Round[]; breaks: RoundBreak[] } {
  const dated: PlottableProposal[] = proposals
    .map((proposal) => {
      const date = parseFilingDate(proposal.date_text, proposal.date_resolved);
      return date ? { proposal, date } : null;
    })
    .filter((p): p is PlottableProposal => p !== null)
    .sort((a, b) => a.date.getTime() - b.date.getTime());

  if (dated.length === 0) return { rounds: [], breaks: [] };

  const breakEvents = events
    .filter((e) => ROUND_BREAK_EVENT_TYPES.has(e.event_type))
    .map((event) => ({ event, date: parseEventDate(event) }))
    .filter((e): e is { event: EventRow; date: Date } => e.date !== null);

  const rounds: Round[] = [{ proposals: [dated[0]] }];
  const breaks: RoundBreak[] = [];

  for (let i = 1; i < dated.length; i++) {
    const prev = dated[i - 1];
    const curr = dated[i];
    const gapDays = (curr.date.getTime() - prev.date.getTime()) / (1000 * 60 * 60 * 24);
    const eventsInGap = breakEvents
      .filter((be) => be.date.getTime() > prev.date.getTime() && be.date.getTime() <= curr.date.getTime())
      .map((be) => be.event);

    if (eventsInGap.length > 0 || gapDays > GAP_DAYS_THRESHOLD) {
      breaks.push({ reason: eventsInGap.length > 0 ? "event" : "gap", events: eventsInGap, gapDays });
      rounds.push({ proposals: [curr] });
    } else {
      rounds[rounds.length - 1].proposals.push(curr);
    }
  }

  return { rounds, breaks };
}
