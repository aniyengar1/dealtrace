import { NextRequest, NextResponse } from "next/server";
import { getDealBySlug, getDealSlugById } from "@/lib/queries";

// Dynamic deal routes (page, memo, memo export) all stream behind a
// loading.tsx-backed Suspense boundary or a plain streamed response,
// so calling redirect()/notFound() from inside the route itself never
// reaches the client as a real HTTP status -- only as a script-driven
// client-side navigation. This proxy runs before any of that, so it's
// the only place a duplicate deal's slug can actually produce a real
// 308 for crawlers, curl, and anything else that doesn't execute JS.
async function redirectDuplicateDeal(request: NextRequest): Promise<NextResponse | null> {
  const segments = request.nextUrl.pathname.split("/").filter(Boolean);
  const [, slug, ...rest] = segments;
  if (!slug) return null;

  const deal = await getDealBySlug(slug);
  if (!deal || deal.is_canonical || !deal.duplicate_of) return null;

  const canonicalSlug = await getDealSlugById(deal.duplicate_of);
  if (!canonicalSlug || canonicalSlug === slug) return null;

  const url = request.nextUrl.clone();
  url.pathname = ["", "deals", canonicalSlug, ...rest].join("/");
  return NextResponse.redirect(url, 308);
}

// Pass-through for now -- no auth exists yet. The matcher already scopes
// this to the review routes so turning on real auth later (check a
// session cookie, redirect to a login page if absent) is a change
// confined to this one file.
export async function proxy(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/deals/")) {
    const redirect = await redirectDuplicateDeal(request);
    if (redirect) return redirect;
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/review/:path*", "/deals/:slug", "/deals/:slug/memo", "/deals/:slug/memo/export"],
};
