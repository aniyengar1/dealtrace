// Port of src/entity_match.py (the Python pipeline's fuzzy company-name
// matching, used by acquirer-guessing, dedup, and headline stats alike)
// -- kept in lockstep with that file so a TypeScript consumer resolving
// "is this proposer actually just the target under an informal name"
// gets the same answer the pipeline's own canonical stats do. See
// canonicalStats.ts for why this exists at all.

const PAREN_SUFFIX_RE = /[/\\][^/\\]*[/\\]/g;
const LEGAL_SUFFIX_RE =
  /\b(incorporated|inc|corporation|corp|company|co|limited|ltd|l\.l\.c|llc|l\.p|lp|plc|holdings?|group|international|technologies|systems?)\b\.?/gi;
const PUNCT_RE = /[^\w\s]/g;
const SPACE_RE = /\s+/g;

export function coreName(name: string): string {
  let n = name.trim().toLowerCase();
  n = n.replace(PAREN_SUFFIX_RE, " ");
  n = n.replace(LEGAL_SUFFIX_RE, " ");
  n = n.replace(PUNCT_RE, " ");
  return n.replace(SPACE_RE, " ").trim();
}

export function isSameEntity(nameA: string, nameB: string): boolean {
  if (!nameA || !nameB) return false;
  const a = coreName(nameA);
  const b = coreName(nameB);
  if (!a || !b) return false;
  if (a === b) return true;
  const [shorter, longer] = a.length <= b.length ? [a, b] : [b, a];
  return shorter.length >= 3 && longer.startsWith(shorter);
}

export function initials(name: string): string {
  const words = coreName(name).split(" ").filter(Boolean);
  return words.map((w) => w[0]).join("").toUpperCase();
}

function initialsIncludingSuffix(name: string): string {
  let n = name.trim().toLowerCase().replace(/&/g, " and ");
  n = n.replace(PAREN_SUFFIX_RE, " ");
  n = n.replace(PUNCT_RE, " ");
  const words = n.replace(SPACE_RE, " ").trim().split(" ").filter(Boolean);
  return words.map((w) => w[0]).join("").toUpperCase();
}

const ANONYMIZED_PLACEHOLDER_RE =
  /^(the\s+)?(company|party|bidder|buyer|acquiror|acquirer|counterparty|sponsor)\s*[a-z0-9]{1,3}$/i;

export function isAnonymizedPlaceholder(name: string): boolean {
  if (!name) return false;
  return ANONYMIZED_PLACEHOLDER_RE.test(name.trim());
}

export function isAcronymOf(short: string, longName: string): boolean {
  const s = short.trim();
  if (!s || !/^[a-zA-Z]+$/.test(s) || s.length < 2 || s.length > 6) return false;
  const words = coreName(longName).split(" ").filter(Boolean);
  if (words.length < 2) return false;
  const upper = s.toUpperCase();
  return upper === initials(longName) || upper === initialsIncludingSuffix(longName);
}

// src/dedup_deals.py's _GENERIC_ACQUIRER_TERMS -- an unresolved
// "Parent"/"Merger Sub"/etc. is never a real answer for "who's the
// acquirer," whether it's being compared to another deal (dedup) or
// surfaced in the UI (the deal ticker).
const GENERIC_ACQUIRER_TERMS = new Set([
  "unknown",
  "parent",
  "merger sub",
  "acquiror",
  "buyer",
  "consortium",
  "sponsor",
]);

export function isGenericAcquirerTerm(name: string): boolean {
  return GENERIC_ACQUIRER_TERMS.has(coreName(name));
}

// src/validate.py's _TARGET_DEFINED_TERMS -- generic structural
// references ("the Company", "Board", "Special Committee") that stand
// in for the target itself in extracted text.
const TARGET_DEFINED_TERMS = new Set([
  "the company",
  "the company's",
  "company",
  "board",
  "board of directors",
  "transaction committee",
  "special committee",
]);

// src/bulk_stats.py's _resolve_target -- a proposer/recipient name that's
// really just the target under a defined term, an entity-match, or an
// acronym should compare equal to the target, not count as a distinct
// third party.
export function resolveTarget(name: string | null, target: string): string | null {
  if (!name) return name;
  const normalized = name.trim().toLowerCase();
  if (TARGET_DEFINED_TERMS.has(normalized) || isSameEntity(name, target) || isAcronymOf(name, target)) {
    return target;
  }
  return name;
}
