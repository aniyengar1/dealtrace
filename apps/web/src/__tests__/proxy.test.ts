import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { NextRequest } from "next/server";

// proxy.ts imports @/lib/queries -> @/lib/db, which is "server-only" --
// a real guard against importing it from a Client Component, but one
// that throws unconditionally outside Next's own RSC compilation (i.e.
// under plain Vitest). None of these tests ever reach a code path that
// actually calls into @/lib/db (every path tested here short-circuits
// in the crosscheck/review gate before resolveDealSlug would run), so
// stubbing the guard out is safe -- same pattern reader.test.ts uses.
vi.mock("server-only", () => ({}));

import { proxy, isGatedCrosscheckPath } from "../proxy";

function request(pathname: string): NextRequest {
  return new NextRequest(new URL(pathname, "http://localhost:3000"));
}

describe("isGatedCrosscheckPath", () => {
  it("gates /crosscheck and /crosscheck/[ticker]", () => {
    expect(isGatedCrosscheckPath("/crosscheck")).toBe(true);
    expect(isGatedCrosscheckPath("/crosscheck/AAPL")).toBe(true);
  });

  it("gates every /api/crosscheck/[ticker] path", () => {
    expect(isGatedCrosscheckPath("/api/crosscheck/AAPL")).toBe(true);
  });

  it("never gates /crosscheck/predictions or anything under it", () => {
    expect(isGatedCrosscheckPath("/crosscheck/predictions")).toBe(false);
    expect(isGatedCrosscheckPath("/crosscheck/predictions/methodology")).toBe(false);
  });
});

describe("proxy() crosscheck gate", () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("404s /crosscheck when the env var is unset", async () => {
    const res = await proxy(request("/crosscheck"));
    expect(res.status).toBe(404);
    const body = await res.text();
    expect(body).toContain("Not available");
    expect(body).toContain("/crosscheck/predictions");
  });

  it("404s /crosscheck/[ticker] when the env var is unset", async () => {
    const res = await proxy(request("/crosscheck/AAPL"));
    expect(res.status).toBe(404);
  });

  it("404s /api/crosscheck/[ticker] when the env var is unset", async () => {
    const res = await proxy(request("/api/crosscheck/AAPL"));
    expect(res.status).toBe(404);
  });

  it("passes /crosscheck through once the env var is set to true", async () => {
    vi.stubEnv("CROSSCHECK_RESEARCH_ENABLED", "true");
    const res = await proxy(request("/crosscheck"));
    expect(res.status).toBe(200);
  });

  it("never gates /crosscheck/predictions, env var set or not", async () => {
    const unset = await proxy(request("/crosscheck/predictions"));
    expect(unset.status).toBe(200);
    vi.stubEnv("CROSSCHECK_RESEARCH_ENABLED", "true");
    const set = await proxy(request("/crosscheck/predictions"));
    expect(set.status).toBe(200);
  });

  it("never gates /crosscheck/predictions/methodology", async () => {
    const res = await proxy(request("/crosscheck/predictions/methodology"));
    expect(res.status).toBe(200);
  });
});
