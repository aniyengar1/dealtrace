import { NextResponse } from "next/server";
import { listCanonicalDealMetrics, filterAndSort, type SortKey } from "@/lib/dealMetrics";
import { CONSIDERATION_TYPE_LABELS, type PriceBucket } from "@/lib/dealLabels";
import { toCsv } from "@/lib/csv";

export const dynamic = "force-dynamic";

// Same filters as /deals itself (reads the same query string), minus
// pagination -- a CSV export should be the whole filtered set, not
// just whichever page the reader happened to be looking at. Public
// fields only: no internal ids, no run/review metadata.
export async function GET(request: Request) {
  const sp = new URL(request.url).searchParams;
  const allRows = await listCanonicalDealMetrics();
  const rows = filterAndSort(allRows, {
    q: sp.get("q") ?? undefined,
    year: sp.get("year") ?? undefined,
    considerationType: sp.get("consideration") ?? undefined,
    priceBucket: (sp.get("price") as PriceBucket) ?? undefined,
    sort: (sp.get("sort") as SortKey) ?? undefined,
    dir: sp.get("dir") === "asc" ? "asc" : "desc",
  });

  const csv = toCsv(
    ["target", "acquirer", "signing_date", "consideration", "price_per_share", "bidders", "proposals", "pct_bump"],
    rows.map((r) => [
      r.targetDisplay,
      r.acquirerDisplay,
      r.signingDate,
      r.considerationType ? CONSIDERATION_TYPE_LABELS[r.considerationType] ?? r.considerationType : null,
      r.pricePlausible === false ? null : r.finalPrice,
      r.nBidders,
      r.nProposals,
      r.pctBump,
    ])
  );

  return new NextResponse(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": 'attachment; filename="dealtrace-deals.csv"',
    },
  });
}
