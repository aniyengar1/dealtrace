import { describe, expect, it } from "vitest";
import { computeDealSummary } from "../dealSummary";
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

const TARGET = "Target Inc";
const ACQUIRER = "Acquirer Co";

describe("computeDealSummary -- new cross-deal/memo fields", () => {
  const proposals: ProposalRow[] = [
    proposal({ date_text: "January 1, 2022", date_resolved: "2022-01-01", proposer: ACQUIRER, status: "superseded", price_low: 100, price_high: 100 }),
    proposal({ date_text: "February 1, 2022", date_resolved: "2022-02-01", proposer: TARGET, status: "open", price_low: 130, price_high: 130, proposal_kind: "counteroffer" }),
    proposal({ date_text: "March 1, 2022", date_resolved: "2022-03-01", proposer: ACQUIRER, status: "accepted", price_low: 121, price_high: 121, premium_pct: 25.0 }),
  ];
  const events: EventRow[] = [
    event({ event_type: "first_contact", date_start: "2021-12-01" }),
    event({ event_type: "signing", date_start: "2022-03-05" }),
    event({ event_type: "activist", date_start: "2021-11-01", summary: "An activist fund urged a sale." }),
  ];

  const summary = computeDealSummary(events, proposals, TARGET);

  it("counts the target's own counteroffers separately from bidder bids", () => {
    expect(summary.nCounteroffers).toBe(1);
    expect(summary.counterofferProposals).toHaveLength(1);
    expect(summary.counterofferProposals[0].proposer).toBe(TARGET);
  });

  it("counts only priced bidder-side proposals as bids", () => {
    expect(summary.nBidderBids).toBe(2); // the two Acquirer Co proposals, not the target's counter
  });

  it("reads the final premium off the final (accepted) proposal", () => {
    expect(summary.finalPremiumPct).toBe(25.0);
  });

  it("flags activist involvement when an activist event exists", () => {
    expect(summary.hasActivist).toBe(true);
    expect(summary.firstActivistEvent?.event_type).toBe("activist");
  });

  it("computes days between the first and final bid, not first-contact-to-signing", () => {
    // Jan 1 -> Mar 1 is 59 days; first-contact-to-signing (Dec 1 -> Mar 5) is a different, larger number.
    expect(summary.daysFirstBidToFinalBid).toBe(59);
    expect(summary.daysFirstContactToSigning).not.toBe(summary.daysFirstBidToFinalBid);
  });

  it("exposes the fact objects each headline figure was read from", () => {
    expect(summary.firstBidProposal?.price_low).toBe(100);
    expect(summary.finalBidProposal?.status).toBe("accepted");
    expect(summary.signingEvent?.date_start).toBe("2022-03-05");
    expect(summary.firstContactEvent?.date_start).toBe("2021-12-01");
  });
});

describe("computeDealSummary -- no activist, no market check event, no counteroffers", () => {
  const proposals: ProposalRow[] = [
    proposal({ date_text: "January 1, 2022", date_resolved: "2022-01-01", proposer: ACQUIRER, status: "accepted", price_low: 50, price_high: 50 }),
  ];
  const summary = computeDealSummary([], proposals, TARGET);

  it("defaults hasActivist to false with no activist event", () => {
    expect(summary.hasActivist).toBe(false);
    expect(summary.firstActivistEvent).toBeNull();
  });

  it("defaults nCounteroffers to 0 with no target-side proposal", () => {
    expect(summary.nCounteroffers).toBe(0);
    expect(summary.counterofferProposals).toEqual([]);
  });

  it("marks market check unknown with a single bidder and no market_check_decision event", () => {
    expect(summary.marketCheck).toBe("unknown");
  });
});

describe("computeDealSummary -- unreviewed marking", () => {
  it("flags bidStatsUnreviewed when any included proposal is unreviewed", () => {
    const proposals: ProposalRow[] = [
      proposal({ date_text: "Jan 1, 2022", date_resolved: "2022-01-01", proposer: ACQUIRER, price_low: 10, price_high: 10, review_status: "unreviewed" }),
    ];
    const summary = computeDealSummary([], proposals, TARGET);
    expect(summary.bidStatsUnreviewed).toBe(true);
  });

  it("clears bidStatsUnreviewed once every included proposal is confirmed", () => {
    const proposals: ProposalRow[] = [
      proposal({ date_text: "Jan 1, 2022", date_resolved: "2022-01-01", proposer: ACQUIRER, price_low: 10, price_high: 10, review_status: "confirmed" }),
    ];
    const summary = computeDealSummary([], proposals, TARGET);
    expect(summary.bidStatsUnreviewed).toBe(false);
  });

  it("flags activistUnreviewed independently of bidStatsUnreviewed", () => {
    const events: EventRow[] = [
      event({ event_type: "activist", date_start: "2021-01-01", review_status: "unreviewed" }),
    ];
    const proposals: ProposalRow[] = [
      proposal({ date_text: "Jan 1, 2022", date_resolved: "2022-01-01", proposer: ACQUIRER, price_low: 10, price_high: 10, review_status: "confirmed" }),
    ];
    const summary = computeDealSummary(events, proposals, TARGET);
    expect(summary.activistUnreviewed).toBe(true);
    expect(summary.bidStatsUnreviewed).toBe(false);
  });
});
