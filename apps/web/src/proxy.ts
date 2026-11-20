import { NextRequest, NextResponse } from "next/server";
import { listDealSlugIndex } from "@/lib/queries";

// Dynamic deal routes (page, memo, memo export) all stream behind a
// loading.tsx-backed Suspense boundary or a plain streamed response,
// so calling redirect()/notFound() from inside the route itself never
// reaches the client as a real HTTP status -- only as a script-driven
// client-side navigation. This proxy runs before any of that, so it's
// the only place a duplicate deal's slug can actually produce a real
// 308, and a nonexistent slug a real 404, for crawlers, curl, and
// anything else that doesn't execute JS.

const SLUG_MAP_TTL_MS = 5 * 60 * 1000;

type SlugEntry = { canonicalSlug: string | null };

let slugMapCache: Map<string, SlugEntry> | null = null;
let slugMapCachedAt = 0;

async function loadSlugMap(): Promise<Map<string, SlugEntry>> {
  const rows = await listDealSlugIndex();
  const slugById = new Map(rows.map((r) => [r.id, r.slug]));
  const map = new Map<string, SlugEntry>();
  for (const row of rows) {
    const canonicalSlug =
      !row.is_canonical && row.duplicate_of ? slugById.get(row.duplicate_of) ?? null : null;
    map.set(row.slug, { canonicalSlug });
  }
  return map;
}

// One query per TTL window, shared across every request in this server
// instance, instead of two queries (getDealBySlug + getDealSlugById) on
// every single deal-page request.
async function getSlugMap(): Promise<Map<string, SlugEntry>> {
  const now = Date.now();
  if (!slugMapCache || now - slugMapCachedAt > SLUG_MAP_TTL_MS) {
    slugMapCache = await loadSlugMap();
    slugMapCachedAt = now;
  }
  return slugMapCache;
}

async function resolveDealSlug(request: NextRequest): Promise<NextResponse | null> {
  const segments = request.nextUrl.pathname.split("/").filter(Boolean);
  const [, slug, ...rest] = segments;
  if (!slug) return null;

  const map = await getSlugMap();
  const entry = map.get(slug);
  if (!entry) {
    return new NextResponse("Not found", {
      status: 404,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }
  if (entry.canonicalSlug && entry.canonicalSlug !== slug) {
    const url = request.nextUrl.clone();
    url.pathname = ["", "deals", entry.canonicalSlug, ...rest].join("/");
    return NextResponse.redirect(url, 308);
  }
  return null;
}

// Pass-through for now -- no auth exists yet. The matcher already scopes
// this to the review routes so turning on real auth later (check a
// session cookie, redirect to a login page if absent) is a change
// confined to this one file.
export async function proxy(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/deals/")) {
    const result = await resolveDealSlug(request);
    if (result) return result;
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/review/:path*", "/deals/:slug", "/deals/:slug/memo", "/deals/:slug/memo/export"],
};
