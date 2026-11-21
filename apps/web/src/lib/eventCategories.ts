// Coarse groupings of schemas.py's ~20 event_type values into the small
// accessible chart palette -- one color per exact type would exceed any
// palette a reader could actually distinguish, so types that play a
// similar role in the narrative (e.g. every board-governance step) share
// a lane and a color on the horizontal timeline.
export type EventCategory = "contact" | "diligence" | "governance" | "bid" | "conclusion" | "other";

export const EVENT_CATEGORY_LABELS: Record<EventCategory, string> = {
  contact: "Contact",
  diligence: "Diligence",
  governance: "Governance",
  bid: "Bids & exclusivity",
  conclusion: "Signing & conclusion",
  other: "Other",
};

// --color-lane-* (globals.css), not --color-chart-* -- the chart ramp's
// brightest step is near-white, which read as one stark lane next to
// five gray ones; the lane ramp stays within a muted mid-gray band so
// every lane is distinct but none is stark.
export const EVENT_CATEGORY_COLORS: Record<EventCategory, string> = {
  contact: "var(--color-lane-1)",
  diligence: "var(--color-lane-2)",
  governance: "var(--color-lane-3)",
  bid: "var(--color-lane-4)",
  conclusion: "var(--color-lane-5)",
  other: "var(--color-lane-6)",
};

const CATEGORY_BY_TYPE: Record<string, EventCategory> = {
  first_contact: "contact",
  discussion: "contact",
  advisor_engagement: "contact",
  re_engagement: "contact",
  nda: "diligence",
  diligence: "diligence",
  diligence_request: "diligence",
  projections_shared: "diligence",
  management_condition: "diligence",
  board_meeting: "governance",
  board_authorization: "governance",
  board_approval: "governance",
  market_check_decision: "governance",
  activist: "governance",
  proposal: "bid",
  counteroffer: "bid",
  withdrawal: "bid",
  rejection: "bid",
  exclusivity: "bid",
  signing: "conclusion",
  draft_agreement: "conclusion",
  announcement: "conclusion",
};

export function eventCategory(eventType: string): EventCategory {
  return CATEGORY_BY_TYPE[eventType] ?? "other";
}
