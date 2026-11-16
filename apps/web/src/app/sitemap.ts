import type { MetadataRoute } from "next";
import { query } from "@/lib/db";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-dynamic";

const STATIC_ROUTES = ["", "/deals", "/stats", "/methodology"];

// Canonical deals only -- a duplicate's slug permanently redirects
// (see deals/[slug]/page.tsx), so listing it here would just hand
// crawlers a URL that immediately 308s away.
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const deals = await query<{ slug: string }>(`SELECT slug FROM deals WHERE is_canonical ORDER BY slug`);

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
