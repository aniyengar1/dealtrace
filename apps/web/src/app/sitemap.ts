import type { MetadataRoute } from "next";
import { query } from "@/lib/db";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-dynamic";

const STATIC_ROUTES = ["", "/deals", "/stats", "/methodology"];

// Included deals only -- canonical (a duplicate's slug permanently
// redirects, see deals/[slug]/page.tsx, so listing it here would just
// hand crawlers a URL that immediately 308s away) AND not
// excluded_from_stats (a spin-off/affiliated-merger/buyer-side-filer
// deal 404s on its own page, so it must not be offered as a URL here
// either).
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const deals = await query<{ slug: string }>(
    `SELECT d.slug FROM deals d JOIN deal_metrics dm ON dm.deal_id = d.id
     WHERE d.is_canonical AND NOT dm.excluded_from_stats ORDER BY d.slug`
  );

  const staticEntries: MetadataRoute.Sitemap = STATIC_ROUTES.map((path) => ({
    url: `${SITE_URL}${path}`,
    changeFrequency: "daily",
    priority: path === "" ? 1 : 0.8,
  }));

  const dealEntries: MetadataRoute.Sitemap = deals.map((d) => ({
    url: `${SITE_URL}/deals/${d.slug}`,
    changeFrequency: "weekly",
    priority: 0.6,
  }));

  return [...staticEntries, ...dealEntries];
}
