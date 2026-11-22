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

type SlugEntry = { canonicalSlug: string | null; excluded: boolean };

let slugMapCache: Map<string, SlugEntry> | null = null;
let slugMapCachedAt = 0;

async function loadSlugMap(): Promise<Map<string, SlugEntry>> {
  const rows = await listDealSlugIndex();
  const slugById = new Map(rows.map((r) => [r.id, r.slug]));
  // Not public either way: excluded_from_stats (a spin-off/affiliated-
  // merger/buyer-side-filer deal) or no completed extraction run at
  // all (Twitter/Musk, New Relic -- nothing to show beyond a bare row).
  const notPublicById = new Map(rows.map((r) => [r.id, r.excluded_from_stats || !r.has_completed_run]));
  const map = new Map<string, SlugEntry>();
  for (const row of rows) {
    const canonicalSlug =
      !row.is_canonical && row.duplicate_of ? slugById.get(row.duplicate_of) ?? null : null;
    // A duplicate's own excluded_from_stats/has_completed_run is
    // meaningless (deal_metrics only computes these for the canonical
    // row) -- what matters is whether the deal this slug actually
    // resolves to is public, so a duplicate of a non-public deal 404s
    // directly instead of redirecting into a canonical page that would
    // just 404 anyway.
    const excluded = row.is_canonical
      ? row.excluded_from_stats || !row.has_completed_run
      : notPublicById.get(row.duplicate_of ?? "") ?? (row.excluded_from_stats || !row.has_completed_run);
    map.set(row.slug, { canonicalSlug, excluded });
  }
  return map;
}

// Styled to match the site's black/silver theme -- this runs in
// middleware, before any Next.js page/layout renders, so it can't reuse
// globals.css or any component; it's the ONLY 404 real browsers and
// crawlers actually see for a bad /deals/:slug request (see this file's
// top comment), so it needs to look intentional on its own. Also reused
// for every other env-var-gated route below (/review, /crosscheck
// research pages) -- the title/message/link are parameterized so a
// gated section doesn't show "Deal not found" copy that makes no sense
// for it, while every caller keeps the same deal-themed defaults it
// already had if it passes nothing.
function notFoundResponse(options?: { title?: string; message?: string; linkHref?: string; linkText?: string }): NextResponse {
  const title = options?.title ?? "Deal not found";
  const message = options?.message ?? "This deal doesn&rsquo;t exist, or isn&rsquo;t part of DealTrace&rsquo;s public dataset.";
  const linkHref = options?.linkHref ?? "/deals";
  const linkText = options?.linkText ?? "&larr; Back to deals";
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${title} · DealTrace</title>
<style>
  html, body { height: 100%; margin: 0; }
  body {
    background: #0a0a0b; color: #f2f2f3;
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    display: flex; align-items: center; justify-content: center;
  }
  .card { max-width: 28rem; text-align: center; padding: 2rem; }
  h1 { font-size: 1.5rem; font-weight: 600; margin: 0 0 0.5rem; }
  p { color: #8b8e94; font-size: 0.95rem; margin: 0 0 1.5rem; }
  a {
    display: inline-block; background: #c0c4cc; color: #0a0a0b;
    text-decoration: none; font-weight: 500; font-size: 0.875rem;
    padding: 0.5rem 1rem; border-radius: 6px;
  }
  a:hover { background: #e5e7eb; }
</style>
</head>
<body>
  <div class="card">
    <h1>${title}</h1>
    <p>${message}</p>
    <a href="${linkHref}">${linkText}</a>
  </div>
</body>
</html>`;
  return new NextResponse(html, {
    status: 404,
    headers: { "content-type": "text/html; charset=utf-8" },
  });
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

// Literal route segments that live directly under /deals/ alongside
// the [slug] dynamic segment -- Next's router already prefers the
// static route for an exact match, but this proxy's own matcher
// (/deals/:slug) can't tell "export" from a real deal slug, so without
// this guard a request for /deals/export would 404 here before the
// real route.ts ever got a chance to run.
const RESERVED_DEALS_SEGMENTS = new Set(["export"]);

async function resolveDealSlug(request: NextRequest): Promise<NextResponse | null> {
  const segments = request.nextUrl.pathname.split("/").filter(Boolean);
  const [, slug, ...rest] = segments;
  if (!slug || RESERVED_DEALS_SEGMENTS.has(slug)) return null;

  const map = await getSlugMap();
  const entry = map.get(slug);
  if (!entry || entry.excluded) {
    return notFoundResponse();
  }
  if (entry.canonicalSlug && entry.canonicalSlug !== slug) {
    const url = request.nextUrl.clone();
    url.pathname = ["", "deals", entry.canonicalSlug, ...rest].join("/");
    return NextResponse.redirect(url, 308);
  }
  return null;
}

// /crosscheck's company-research pages (and the API route behind them)
// read companies/earnings_company_reports/earnings_quarter_calculations/
// guidance_versions/earnings_actuals over the shared DATABASE_URL pool --
// tables scripts/push_to_supabase.sh doesn't copy and dealtrace_web isn't
// granted on yet (see supabase/crosscheck_public.sql), so until that's
// run in production these routes would 500/503 instead of rendering.
// Gated the same way /review is: CROSSCHECK_RESEARCH_ENABLED=true locally,
// left unset on Vercel so they 404 cleanly instead. /crosscheck/predictions
// and its methodology page are a SEPARATE, already-public read path (a
// dedicated CROSSCHECK_PUBLISHED_DATABASE_URL connection to just two
// snapshot tables, see lib/crosscheck/predictions/read.ts) and must stay
// reachable -- excluded here by name, not by the matcher (Next's matcher
// syntax can't express "a dynamic segment except this one literal value").
const CROSSCHECK_PREDICTIONS_PREFIX = "/crosscheck/predictions";

export function isGatedCrosscheckPath(pathname: string): boolean {
  if (pathname.startsWith("/api/crosscheck/")) return true;
  if (pathname.startsWith(CROSSCHECK_PREDICTIONS_PREFIX)) return false;
  return pathname === "/crosscheck" || pathname.startsWith("/crosscheck/");
}

// /review has no real auth yet, so it's gated behind an env var instead
// of being reachable by anyone who guesses a slug: REVIEW_ENABLED=true
// locally (see .env.example), left unset on Vercel so the whole review
// queue 404s in production. Swapping this for real auth later (check a
// session cookie, redirect to a login page if absent) is a change
// confined to this one file -- the matcher already scopes it to the
// review routes.
export async function proxy(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/review")) {
    if (process.env.REVIEW_ENABLED !== "true") {
      return notFoundResponse();
    }
    return NextResponse.next();
  }
  if (isGatedCrosscheckPath(request.nextUrl.pathname)) {
    if (process.env.CROSSCHECK_RESEARCH_ENABLED !== "true") {
      return notFoundResponse({
        title: "Not available",
        message: "This Crosscheck research page isn&rsquo;t public yet.",
        linkHref: "/crosscheck/predictions",
        linkText: "&larr; Locked predictions",
      });
    }
    return NextResponse.next();
  }
  if (request.nextUrl.pathname.startsWith("/deals/")) {
    const result = await resolveDealSlug(request);
    if (result) return result;
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/review/:path*",
    "/deals/:slug",
    "/deals/:slug/memo",
    "/deals/:slug/memo/export",
    "/crosscheck",
    "/crosscheck/:ticker",
    "/api/crosscheck/:ticker",
  ],
};
