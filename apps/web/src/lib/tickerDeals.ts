import "server-only";

import { query } from "./db";
import { HAS_COMPLETED_RUN_SQL } from "./dealMetrics";

export interface TickerDeal {
  slug: string;
  targetDisplay: string;
  acquirerDisplay: string;
  finalPrice: number | null;
}

// A fixed, hand-picked list of well-known deals, not a heuristic filter
// over the full bulk-loaded set -- the bulk table's entity matching is
// good enough for cross-deal stats but occasionally resolves an
// acquirer to a ticker symbol or a generic noun, which reads fine
// buried in a histogram n but looks broken scrolling past in a hero
// marquee. Every slug here was checked against deal_metrics: canonical,
// price_plausible, and a single non-null final_price.
const CURATED_TICKER_SLUGS = [
  "splunk",
  "activision",
  "mandiant",
  "citrix",
  "coupa",
  "anaplan",
  "zendesk",
  "cvent",
  "bulk_1124610_000114036122035833", // VMware -> Broadcom
  "bulk_1060736_000119312523112984", // Seagen -> Pfizer
  "bulk_702165_000119312525226601", // Norfolk Southern -> Union Pacific
  "bulk_804753_000119312522012548", // Cerner -> Oracle
  "bulk_899866_000104746921000931", // Alexion Pharmaceuticals -> AstraZeneca
  "bulk_933136_000110465925072383", // Mr. Cooper -> Rocket
  "bulk_1604778_000110465925124244", // Qorvo -> Skyworks
];

export async function getTickerDeals(): Promise<TickerDeal[]> {
  const rows = await query<{
    slug: string;
    target_display: string;
    acquirer_display: string;
    final_price: number | null;
  }>(
    `SELECT d.slug, dm.target_display, dm.acquirer_display, dm.final_price
     FROM deal_metrics dm
     JOIN deals d ON d.id = dm.deal_id
     WHERE d.slug = ANY($1) AND dm.is_canonical AND NOT dm.excluded_from_stats AND ${HAS_COMPLETED_RUN_SQL}
       AND dm.price_plausible IS DISTINCT FROM false AND dm.final_price IS NOT NULL`,
    [CURATED_TICKER_SLUGS]
  );

  const bySlug = new Map(rows.map((r) => [r.slug, r]));
  return CURATED_TICKER_SLUGS.map((slug) => bySlug.get(slug))
    .filter((r): r is NonNullable<typeof r> => r !== undefined)
    .map((r) => ({
      slug: r.slug,
      targetDisplay: r.target_display,
      acquirerDisplay: r.acquirer_display,
      finalPrice: r.final_price,
    }));
}
