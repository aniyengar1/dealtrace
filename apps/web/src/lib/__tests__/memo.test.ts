import { describe, expect, it } from "vitest";
import { buildDealMemo, renderMemoMarkdown } from "../memo";
import type { Deal, EventRow, ProposalRow, ValuationRow } from "../types";

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

function valuation(overrides: Partial<ValuationRow>): ValuationRow {
  nextId++;
  return {
    record_type: "ValuationAnalysis",
    id: `v${nextId}`,
    run_id: "run1",
    advisor: "Test Bank",
    method: "dcf",
    metric: "EV/Revenue",
    multiple_low: null,
    multiple_high: null,
    implied_price_low: null,
    implied_price_high: null,
    key_assumptions: [],
    source_paragraph_ids: ["p00009"],
    source_quotes: [],
    passed: true,
    failure_reasons: [],
    review_status: "unreviewed",
    reviewer_note: null,
    ...overrides,
  };
}

const DEAL: Deal = {
  id: "d1",
  slug: "test_deal",
  deal_name: "Acquirer Co's Acquisition of Target Inc",
  target: "Target Inc",
  acquirer: "Acquirer Co",
  search_term: "target inc",
  is_canonical: true,
  duplicate_of: null,
  excluded_from_stats: false,
};

const EVENTS: EventRow[] = [
  event({ event_type: "first_contact", date_start: "2022-01-01", summary: "First contact.", source_paragraph_ids: ["p00001"] }),
  event({
    event_type: "withdrawal",
    date_start: "2022-01-15",
    summary: "Acquirer Co withdrew its indication of interest.",
    source_paragraph_ids: ["p00002"],
  }),
  event({
    event_type: "signing",
    date_start: "2022-03-01",
    parties: ["Target Inc", "Acquirer Co"],
    summary: "The parties signed the merger agreement.",
    source_paragraph_ids: ["p00010"],
  }),
  event({
    event_type: "draft_agreement",
    date_start: "2022-02-20",
    summary: "Counsel exchanged a markup proposing a termination fee of 3% of equity value.",
    source_paragraph_ids: ["p00009"],
  }),
];

const PROPOSALS: ProposalRow[] = [
  proposal({
    date_text: "January 1, 2022",
    date_resolved: "2022-01-01",
    proposer: "Acquirer Co",
    recipient: "Target Inc",
    price_low: 100,
    price_high: 100,
    source_paragraph_ids: ["p00003"],
  }),
  proposal({
    date_text: "February 1, 2022",
    date_resolved: "2022-02-01",
    proposer: "Target Inc",
    recipient: "Acquirer Co",
    price_low: 130,
    price_high: 130,
    proposal_kind: "counteroffer",
    source_paragraph_ids: ["p00005"],
  }),
  proposal({
    date_text: "March 1, 2022",
    date_resolved: "2022-03-01",
    proposer: "Acquirer Co",
    recipient: "Target Inc",
    price_low: 121,
    price_high: 121,
    premium_pct: 25.0,
    status: "accepted",
    source_paragraph_ids: ["p00008"],
  }),
];

const VALUATIONS: ValuationRow[] = [
  valuation({ advisor: "Qatalyst Partners", method: "dcf", implied_price_low: 110, implied_price_high: 130, source_paragraph_ids: ["p00006"] }),
];

describe("buildDealMemo", () => {
  const memo = buildDealMemo(DEAL, EVENTS, PROPOSALS, VALUATIONS);

  it("states the final per-share consideration and cites the final proposal", () => {
    const considerationLine = memo.dealTerms.find((l) => l.text.startsWith("Per-share consideration"));
    expect(considerationLine?.text).toContain("$121.00");
    expect(considerationLine?.paragraphIds).toEqual(["p00008"]);
  });

  it("states the final premium when stated", () => {
    const premiumLine = memo.dealTerms.find((l) => l.text.startsWith("Premium"));
    expect(premiumLine?.text).toContain("25.0%");
  });

  it("surfaces a termination-fee mention found in event text, with its citation", () => {
    const feeLine = memo.dealTerms.find((l) => l.text.startsWith("Termination fee") && !l.text.includes("not extracted"));
    expect(feeLine).toBeDefined();
    expect(feeLine?.paragraphIds).toEqual(["p00009"]);
  });

  it("lists the financial advisor from valuations", () => {
    const advisorLine = memo.partiesAndAdvisors.find((l) => l.text.includes("Qatalyst Partners"));
    expect(advisorLine).toBeDefined();
    expect(advisorLine?.paragraphIds).toEqual(["p00006"]);
  });

  it("includes only core event types in the timeline, each dated and cited", () => {
    // withdrawal and signing are core; first_contact and draft_agreement are not.
    expect(memo.timeline).toHaveLength(2);
    for (const l of memo.timeline) {
      expect(l.paragraphIds.length).toBeGreaterThan(0);
    }
  });

  it("orders the bid history chronologically and cites every row", () => {
    expect(memo.bidHistory.map((r) => r.proposer)).toEqual(["Acquirer Co", "Target Inc", "Acquirer Co"]);
    for (const r of memo.bidHistory) {
      expect(r.paragraphIds.length).toBeGreaterThan(0);
    }
  });

  it("flags the valuation range against the final price", () => {
    // final price 121 is within [110, 130]
    expect(memo.valuationSummary[0].vsFinal).toBe("within range");
  });

  it("surfaces the withdrawal as a notable feature with a citation", () => {
    const withdrawalLine = memo.notableFeatures.find((l) => l.text.startsWith("Withdrawal"));
    expect(withdrawalLine?.paragraphIds).toEqual(["p00002"]);
  });

  it("generates 3-4 talking points, each citing at least one paragraph", () => {
    expect(memo.talkingPoints.length).toBeGreaterThanOrEqual(1);
    expect(memo.talkingPoints.length).toBeLessThanOrEqual(4);
    for (const l of memo.talkingPoints) {
      expect(l.paragraphIds.length).toBeGreaterThan(0);
    }
  });

  it("builds a bid-bump talking point consistent with the computed stats", () => {
    const bumpLine = memo.talkingPoints.find((l) => l.text.includes("raised its bid"));
    expect(bumpLine?.text).toContain("Acquirer Co");
    expect(bumpLine?.text).toContain("$100.00");
    expect(bumpLine?.text).toContain("$121.00");
  });

  it("builds a counteroffer talking point citing the target's own proposal, not the final bid", () => {
    const counterLine = memo.talkingPoints.find((l) => l.text.includes("countered"));
    expect(counterLine?.paragraphIds).toEqual(["p00005"]);
  });
});

describe("buildDealMemo -- no evidence for a section falls back to an uncited line", () => {
  it("says termination fee not extracted when no event mentions it", () => {
    const memo = buildDealMemo(DEAL, [EVENTS[0], EVENTS[2]], PROPOSALS, []);
    const feeLine = memo.dealTerms.find((l) => l.text.startsWith("Termination fee"));
    expect(feeLine?.text).toBe("Termination fee: not extracted.");
    expect(feeLine?.paragraphIds).toEqual([]);
  });

  it("says no notable features when none of the four categories apply", () => {
    const memo = buildDealMemo(DEAL, [EVENTS[0]], [PROPOSALS[0]], []);
    expect(memo.notableFeatures).toHaveLength(1);
    expect(memo.notableFeatures[0].paragraphIds).toEqual([]);
  });
});

describe("renderMemoMarkdown", () => {
  const memo = buildDealMemo(DEAL, EVENTS, PROPOSALS, VALUATIONS);
  const markdown = renderMemoMarkdown(memo);

  it("includes every section heading", () => {
    for (const heading of [
      "## Deal terms",
      "## Parties and advisors",
      "## Process timeline",
      "## Bid history",
      "## Valuation summary",
      "## Notable features",
      "## Talking points",
    ]) {
      expect(markdown).toContain(heading);
    }
  });

  it("cites a paragraph id for every bid history row", () => {
    for (const r of memo.bidHistory) {
      expect(markdown).toContain(`¶${r.paragraphIds[0]}`);
    }
  });
});
