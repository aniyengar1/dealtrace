import "server-only";

import type { DealSummary } from "./types";
import { isAnonymizedPlaceholder, isGenericAcquirerTerm, isSameEntity } from "./entityMatch";

const COMMITTEE_RE = /\bcommittee\b/i;

// A deal only belongs in the ticker if it has a real, resolved acquirer
// name -- never a generic placeholder ("Parent", "Unknown"), an
// anonymized filing label ("Company A", "Party B"), a board/deal
// committee ("Conflicts Committee", "Special Committee"), or the target
// itself under a slightly different name (entity-matched, not just
// exact string equality).
function hasRealAcquirer(deal: DealSummary): boolean {
  const acquirer = deal.acquirer?.trim();
  if (!acquirer) return false;
  if (isGenericAcquirerTerm(acquirer)) return false;
  if (isAnonymizedPlaceholder(acquirer)) return false;
  if (COMMITTEE_RE.test(acquirer)) return false;
  if (isSameEntity(acquirer, deal.target)) return false;
  return true;
}

const MAX_TICKER_ITEMS = 40;

export function selectTickerDeals(deals: DealSummary[]): DealSummary[] {
  const eligible = deals.filter(
    (d) =>
      d.is_canonical &&
      (d.final_price_low !== null || d.final_price_high !== null) &&
      hasRealAcquirer(d)
  );

  // Curated (hand-registered, slug not "bulk_...") deals are the
  // well-known names this project started with -- Splunk/Cisco,
  // Zendesk, Activision, etc. -- so they lead the loop; everything else
  // follows in whatever order listDealsSummary already sorted them.
  const curated = eligible.filter((d) => !d.slug.startsWith("bulk_"));
  const bulk = eligible.filter((d) => d.slug.startsWith("bulk_"));

  return [...curated, ...bulk].slice(0, MAX_TICKER_ITEMS);
}
