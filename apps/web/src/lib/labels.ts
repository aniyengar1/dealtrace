// Display-name overrides for the fixed vocabularies in schemas.py --
// snake_case is fine as a DB/API value but not as something a reader
// should see ("nda" -> "NDA", "re_engagement" -> "Re-engagement").

export const EVENT_TYPE_LABELS: Record<string, string> = {
  first_contact: "First contact",
  nda: "NDA",
  proposal: "Proposal",
  counteroffer: "Counteroffer",
  board_meeting: "Board meeting",
  exclusivity: "Exclusivity",
  diligence: "Diligence",
  signing: "Signing",
  other: "Other",
  withdrawal: "Withdrawal",
  re_engagement: "Re-engagement",
  rejection: "Rejection",
  advisor_engagement: "Advisor engagement",
  projections_shared: "Projections shared",
  market_check_decision: "Market check decision",
  board_authorization: "Board authorization",
  board_approval: "Board approval",
  press_leak: "Press leak",
  management_condition: "Management condition",
  draft_agreement: "Draft agreement",
  announcement: "Announcement",
  discussion: "Discussion",
  diligence_request: "Diligence request",
  activist: "Activist",
};

export function eventTypeLabel(type: string): string {
  return EVENT_TYPE_LABELS[type] ?? type.replace(/_/g, " ");
}

// The event types that matter most to a reviewer -- shared by the
// timeline's filter chips and the review queue's ordering/toggle so the
// two views of "what's core" never drift apart.
export const CORE_EVENT_TYPES = new Set([
  "proposal",
  "withdrawal",
  "rejection",
  "exclusivity",
  "signing",
  "board_approval",
]);

export const PROPOSAL_KIND_LABELS: Record<string, string> = {
  non_binding_indication: "Non-binding indication",
  formal_bid: "Formal bid",
  counteroffer: "Counteroffer",
  revised_bid: "Revised bid",
  suggested_valuation: "Suggested valuation",
};

export function proposalKindLabel(kind: string): string {
  return PROPOSAL_KIND_LABELS[kind] ?? kind.replace(/_/g, " ");
}

export const VALUATION_METHOD_LABELS: Record<string, string> = {
  trading_comps: "Trading comparables",
  precedent_transactions: "Precedent transactions",
  dcf: "DCF",
  other: "Other",
};

export function valuationMethodLabel(method: string): string {
  return VALUATION_METHOD_LABELS[method] ?? method.replace(/_/g, " ");
}

export const PROPOSAL_STATUS_LABELS: Record<string, string> = {
  open: "Open",
  rejected: "Rejected",
  superseded: "Superseded",
  accepted: "Accepted",
  withdrawn: "Withdrawn",
};

export function proposalStatusLabel(status: string): string {
  return PROPOSAL_STATUS_LABELS[status] ?? status.replace(/_/g, " ");
}

// Per-deal acquirer display overrides -- the pipeline's DEALS registry
// uses a short structural placeholder ("Consortium") for a few deals
// where the real acquirer is two or more firms acting jointly; this
// maps the deal slug to what should actually be shown.
export const ACQUIRER_DISPLAY_OVERRIDES: Record<string, string> = {
  zendesk: "Hellman & Friedman / Permira",
};

export function acquirerDisplayName(slug: string, acquirer: string): string {
  return ACQUIRER_DISPLAY_OVERRIDES[slug] ?? acquirer;
}

export type BuyerType = "strategic" | "sponsor" | "unknown";

export const BUYER_TYPE_LABELS: Record<BuyerType, string> = {
  strategic: "Strategic",
  sponsor: "Financial sponsor",
  unknown: "Unknown",
};

// Explicit per-deal classification for every deal in the pipeline's
// registry, not just the ones with a loaded run -- a newly-loaded deal
// should show its correct buyer type immediately, not "Unknown" until
// someone remembers to add it here. Only deals absent from this map
// (none, today) fall through to the acquirer-name heuristic below.
export const BUYER_TYPE_OVERRIDES: Record<string, BuyerType> = {
  splunk: "strategic", // Cisco
  mandiant: "strategic", // Google
  activision: "strategic", // Microsoft
  zendesk: "sponsor", // Hellman & Friedman / Permira consortium
  cvent: "sponsor", // Blackstone
  anaplan: "sponsor", // Thoma Bravo
  citrix: "sponsor", // Vista Equity Partners / Evergreen Coast Capital
  coupa: "sponsor", // Thoma Bravo
  new_relic: "sponsor", // Francisco Partners / TPG
};

// Fallback for a deal slug not yet in BUYER_TYPE_OVERRIDES: common
// private-equity/financial-sponsor naming conventions. Deliberately
// returns "unknown" rather than guessing "strategic" by default -- an
// individual buyer (e.g. "Musk") or an unfamiliar name shouldn't be
// silently miscategorized as either.
const SPONSOR_NAME_PATTERN = /\b(partners|capital|equity|ventures|holdings)\b/i;

export function buyerType(slug: string, acquirer: string): BuyerType {
  if (slug in BUYER_TYPE_OVERRIDES) return BUYER_TYPE_OVERRIDES[slug];
  return SPONSOR_NAME_PATTERN.test(acquirer) ? "sponsor" : "unknown";
}
