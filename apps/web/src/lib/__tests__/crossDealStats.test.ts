import { describe, expect, it } from "vitest";
import { computeDealStatsRow, computeCrossDealSummary, median, mean } from "../crossDealStats";
import type { Deal, EventRow, ProposalRow } from "../types";

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

function deal(overrides: Partial<Deal>): Deal {
  return {
    id: "d1",
    slug: "test_deal",
    deal_name: "Test Deal",
    target: "Target Inc",
    acquirer: "Acquirer Co",
    search_term: "",
    ...overrides,
  };
}

describe("median/mean", () => {
  it("returns null for an empty list", () => {
    expect(median([])).toBeNull();
    expect(mean([])).toBeNull();
  });

  it("computes the midpoint for an even-length list", () => {
    expect(median([1, 2, 3, 4])).toBe(2.5);
  });

  it("computes the middle value for an odd-length list", () => {
    expect(median([5, 1, 3])).toBe(3);
  });

  it("computes a simple average", () => {
    expect(mean([1, 2, 3])).toBe(2);
  });
});

describe("computeDealStatsRow", () => {
  it("returns null for a deal with no events or proposals", () => {
    expect(computeDealStatsRow(deal({}), [], [])).toBeNull();
  });

  it("classifies a known strategic acquirer by slug override", () => {
    const row = computeDealStatsRow(
      deal({ slug: "splunk", acquirer: "Cisco" }),
      [],
      [proposal({ proposer: "Cisco", price_low: 10, price_high: 10, date_text: "Jan 1, 2022", date_resolved: "2022-01-01" })]
    );
    expect(row?.buyerType).toBe("strategic");
  });

  it("classifies a known sponsor acquirer by slug override", () => {
    const row = computeDealStatsRow(
      deal({ slug: "cvent", acquirer: "Blackstone" }),
      [],
      [proposal({ proposer: "Blackstone", price_low: 10, price_high: 10, date_text: "Jan 1, 2022", date_resolved: "2022-01-01" })]
    );
    expect(row?.buyerType).toBe("sponsor");
  });

  it("falls back to the sponsor-name heuristic for an unmapped slug", () => {
    const row = computeDealStatsRow(
      deal({ slug: "some_new_deal", acquirer: "Example Capital Partners" }),
      [],
      [proposal({ proposer: "Example Capital Partners", price_low: 10, price_high: 10, date_text: "Jan 1, 2022", date_resolved: "2022-01-01" })]
    );
    expect(row?.buyerType).toBe("sponsor");
  });

  it("defaults to unknown for an unmapped slug with no sponsor-like name", () => {
    const row = computeDealStatsRow(
      deal({ slug: "some_new_deal", acquirer: "Jane Doe" }),
      [],
      [proposal({ proposer: "Jane Doe", price_low: 10, price_high: 10, date_text: "Jan 1, 2022", date_resolved: "2022-01-01" })]
    );
    expect(row?.buyerType).toBe("unknown");
  });
});

describe("computeCrossDealSummary", () => {
  const strategicDeal = computeDealStatsRow(
    deal({ slug: "splunk", acquirer: "Cisco" }),
    [event({ event_type: "first_contact", date_start: "2022-01-01" }), event({ event_type: "signing", date_start: "2022-01-11" })],
    [
      proposal({ proposer: "Cisco", price_low: 100, price_high: 100, date_text: "Jan 1, 2022", date_resolved: "2022-01-01" }),
      proposal({ proposer: "Cisco", status: "accepted", price_low: 120, price_high: 120, date_text: "Jan 10, 2022", date_resolved: "2022-01-10" }),
    ]
  )!;
  const sponsorDeal = computeDealStatsRow(
    deal({ slug: "cvent", acquirer: "Blackstone" }),
    [event({ event_type: "first_contact", date_start: "2022-01-01" }), event({ event_type: "signing", date_start: "2022-01-21" })],
    [
      proposal({ proposer: "Blackstone", price_low: 100, price_high: 100, date_text: "Jan 1, 2022", date_resolved: "2022-01-01" }),
      proposal({ proposer: "Blackstone", status: "accepted", price_low: 140, price_high: 140, date_text: "Jan 20, 2022", date_resolved: "2022-01-20" }),
    ]
  )!;

  const summary = computeCrossDealSummary([strategicDeal, sponsorDeal]);

  it("reports n at the overall level", () => {
    expect(summary.nDeals).toBe(2);
    expect(summary.overall.n).toBe(2);
  });

  it("splits n and medians by buyer type", () => {
    expect(summary.byBuyerType.strategic.n).toBe(1);
    expect(summary.byBuyerType.sponsor.n).toBe(1);
    expect(summary.byBuyerType.strategic.medianPctChange).toBe(20); // 100 -> 120
    expect(summary.byBuyerType.sponsor.medianPctChange).toBe(40); // 100 -> 140
  });

  it("computes the overall median across both deals", () => {
    expect(summary.overall.medianPctChange).toBe(30); // median of 20 and 40
  });

  it("reports an empty group (n=0) for a buyer type with no deals", () => {
    expect(summary.byBuyerType.unknown.n).toBe(0);
    expect(summary.byBuyerType.unknown.medianPctChange).toBeNull();
  });
});
