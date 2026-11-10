// No auth yet -- this app is local-only. This exists so the review
// routes have one call site to gate later: swap this function's body for
// a real session/JWT check (and middleware.ts's matcher is already
// scoped to /review/:path*), and both the pages and the server actions
// in app/review/[slug]/actions.ts that call it start enforcing it with
// no other code changes.
export async function requireReviewer(): Promise<{ id: string; name: string }> {
  return { id: "local-dev", name: "Local Reviewer" };
}
