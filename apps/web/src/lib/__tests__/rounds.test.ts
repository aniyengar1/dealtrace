import { describe, expect, it } from "vitest";
import { computeRounds } from "../rounds";
import type { EventRow, ProposalRow } from "../types";

let nextId = 0;
function proposal(overrides: Partial<ProposalRow>): ProposalRow {
  nextId++;
  return {
    record_type: "Proposal",
    id: `p${nextId}`,
    run_id: "run1",
    date_text: "",
    date_resolved: null,
    proposer: "",
    recipient: "",
    price_low: null,
    price_high: null,
    premium_pct: null,
    currency: "USD",
    consideration_type: "cash",
    proposal_kind: "non_binding_indication",
    status: "open",
    source_paragraph_ids: ["p00001"],
    source_quotes: [],
    passed: true,
    failure_reasons: [],
    review_status: "unreviewed",
    reviewer_note: null,
    ...overrides,
  };
}

function event(overrides: Partial<EventRow>): EventRow {
  nextId++;
  return {
    record_type: "Event",
    id: `e${nextId}`,
    run_id: "run1",
    date_text: "",
    date_start: null,
    date_end: null,
    date_precision: "day",
    event_type: "other",
    parties: [],
    summary: "",
    source_paragraph_ids: ["p00001"],
    source_quotes: [],
    passed: true,
    failure_reasons: [],
    review_status: "unreviewed",
    reviewer_note: null,
    ...overrides,
  };
}

// Mirrors the real Splunk/Cisco timeline closely enough to exercise the
// algorithm: Cisco's sole December-February approach is flatly
// withdrawn (the only bidder leaves, nobody else is in play -- a real
// break), then re-engages in April 2023 and, despite a rejection along
// the way in June, keeps submitting revised numbers through signing in
// August -- a single continuous round, since Cisco itself never
// actually withdrew again.
describe("computeRounds -- Splunk-shaped data", () => {
  const target = "Splunk";
  const proposals: ProposalRow[] = [
    proposal({ date_text: "December 17, 2021", date_resolved: "2021-12-17", proposer: "Cisco", status: "superseded", price_low: 165, price_high: 175 }),
    proposal({ date_text: "January 14, 2022", date_resolved: "2022-01-14", proposer: "Cisco", status: "superseded", price_low: 175, price_high: 190 }),
    proposal({ date_text: "February 4, 2022", date_resolved: "2022-02-04", proposer: "Cisco", status: "withdrawn", price_low: 193, price_high: 193 }),
    proposal({ date_text: "February 6, 2022", date_resolved: "2022-02-06", proposer: "Splunk", status: "rejected", price_low: 212, price_high: 212 }),
    proposal({ date_text: "June 20, 2023", date_resolved: "2023-06-20", proposer: "Cisco", status: "rejected", price_low: 130, price_high: 130 }),
    proposal({ date_text: "August 25, 2023", date_resolved: "2023-08-25", proposer: "Cisco", status: "superseded", price_low: 142, price_high: 142 }),
    proposal({ date_text: "August 31, 2023", date_resolved: "2023-08-31", proposer: "Cisco", status: "accepted", price_low: 157, price_high: 157 }),
  ];
  const events: EventRow[] = [
    event({ event_type: "withdrawal", date_start: "2022-02-06", summary: "Cisco withdrew its indication of interest to acquire Splunk." }),
    event({ event_type: "re_engagement", date_start: "2023-04-04", summary: "Scott Herren of Cisco contacted Gary Steele to express interest in re-engaging." }),
    event({ event_type: "rejection", date_start: "2023-06-29", summary: "Gary Steele called Chuck Robbins to convey that Splunk's Board rejected Cisco's $130 offer." }),
  ];

  it("produces exactly 2 rounds", () => {
    const { rounds } = computeRounds(proposals, events, target);
    expect(rounds.length).toBe(2);
  });

  it("keeps the mid-negotiation rejection from splitting round 2", () => {
    const { rounds } = computeRounds(proposals, events, target);
    const round2Dates = rounds[1].proposals.map((p) => p.date.toISOString().slice(0, 10));
    expect(round2Dates).toEqual(["2023-06-20", "2023-08-25", "2023-08-31"]);
  });

  it("keeps the target's same-day reactive proposal in the ending round, not the next one", () => {
    const { rounds } = computeRounds(proposals, events, target);
    const round1Dates = rounds[0].proposals.map((p) => p.date.toISOString().slice(0, 10));
    expect(round1Dates).toContain("2022-02-06");
  });
});

// Mirrors the real Zendesk timeline: an unsolicited February proposal
// flatly, publicly rejected (round 1); a formal sale process launched
// in March that runs several bidders through May and June 1 (round 2)
// -- a consortium member leaving (May 9) and the whole Consortium
// withdrawing while Bidder 2 stays in (May 24) are both explicitly not
// breaks; the target publicly ending the review on June 9 followed by
// the Consortium re-engaging on June 14 opens a final round through
// signing on June 21 (round 3).
describe("computeRounds -- Zendesk-shaped data", () => {
  const target = "Zendesk";
  const proposals: ProposalRow[] = [
    proposal({ date_text: "February 7, 2022", date_resolved: "2022-02-07", proposer: "Consortium", status: "rejected", price_low: 127, price_high: 132 }),
    proposal({ date_text: "May 5, 2022", date_resolved: "2022-05-05", proposer: "Consortium", status: "superseded", price_low: 120, price_high: 120 }),
    proposal({ date_text: "May 5, 2022", date_resolved: "2022-05-05", proposer: "Bidder 2", status: "superseded", price_low: 125, price_high: 135 }),
    proposal({ date_text: "May 24, 2022", date_resolved: "2022-05-24", proposer: "Consortium", status: "withdrawn", price_low: 96, price_high: 96 }),
    proposal({ date_text: "June 1, 2022", date_resolved: "2022-06-01", proposer: "Bidder 2", status: "rejected", price_low: 90.12, price_high: 100 }),
    proposal({ date_text: "June 14, 2022", date_resolved: "2022-06-14", proposer: "Consortium", status: "superseded", price_low: 82, price_high: 82 }),
    proposal({ date_text: "June 21, 2022", date_resolved: "2022-06-21", proposer: "Consortium", status: "accepted", price_low: 77.5, price_high: 77.5 }),
  ];
  const events: EventRow[] = [
    event({ event_type: "rejection", date_start: "2022-02-10", summary: "Zendesk issued a press release announcing its rejection of the Consortium's preliminary nonbinding proposal." }),
    event({ event_type: "withdrawal", date_start: "2022-05-09", summary: "The Consortium notified Qatalyst Partners that Financial Sponsor A had withdrawn from the Consortium bidding group." }),
    event({ event_type: "withdrawal", date_start: "2022-05-24", summary: "The Consortium informed Qatalyst Partners that key co-investors and sponsors had withdrawn." }),
    event({ event_type: "announcement", date_start: "2022-06-09", summary: "Zendesk issued a press release announcing the completion of its strategic review process and its decision to remain independent." }),
    event({ event_type: "re_engagement", date_start: "2022-06-14", summary: "Representatives of the Consortium contacted Qatalyst Partners to express renewed interest." }),
  ];

  it("produces exactly 3 rounds", () => {
    const { rounds } = computeRounds(proposals, events, target);
    expect(rounds.length).toBe(3);
  });

  it("keeps Bidder 2 active through the consortium-member and whole-consortium exits", () => {
    const { rounds } = computeRounds(proposals, events, target);
    const round2Dates = rounds[1].proposals.map((p) => p.date.toISOString().slice(0, 10));
    expect(round2Dates).toEqual(["2022-05-05", "2022-05-05", "2022-05-24", "2022-06-01"]);
  });

  it("joins the re-engagement's own date to the restart round, not the round before it", () => {
    const { rounds } = computeRounds(proposals, events, target);
    const round3Dates = rounds[2].proposals.map((p) => p.date.toISOString().slice(0, 10));
    expect(round3Dates).toEqual(["2022-06-14", "2022-06-21"]);
  });

  it("labels the round breaks with their triggering events, de-duplicated", () => {
    const { breaks } = computeRounds(proposals, events, target);
    expect(breaks[0].events.map((e) => e.event_type)).toEqual(["rejection"]);
    expect(breaks[1].events.map((e) => e.event_type).sort()).toEqual(["announcement", "re_engagement"]);
  });
});
