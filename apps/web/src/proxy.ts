import { NextResponse } from "next/server";

// Pass-through for now -- no auth exists yet. The matcher already scopes
// this to the review routes so turning on real auth later (check a
// session cookie, redirect to a login page if absent) is a change
// confined to this one file.
export function proxy() {
  return NextResponse.next();
}

export const config = {
  matcher: ["/review/:path*"],
};
