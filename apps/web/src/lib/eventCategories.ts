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

export const EVENT_CATEGORY_COLORS: Record<EventCategory, string> = {
  contact: "var(--color-chart-1)",
  diligence: "var(--color-chart-2)",
  governance: "var(--color-chart-3)",
  bid: "var(--color-chart-4)",
  conclusion: "var(--color-chart-5)",
  other: "var(--color-chart-6)",
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
