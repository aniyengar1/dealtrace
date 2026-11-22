import { NextResponse } from "next/server";
import { listCanonicalDealMetrics } from "@/lib/dealMetrics";
import { buyerType, BUYER_TYPE_LABELS } from "@/lib/labels";
import { toCsv } from "@/lib/csv";

export const dynamic = "force-dynamic";

// /stats has no filters of its own (just pagination), so this exports
// every included deal's row exactly as the table shows it. Public
// fields only: no internal ids, no run/review metadata.
export async function GET() {
  const rows = await listCanonicalDealMetrics();

  const csv = toCsv(
    ["target", "acquirer", "buyer_type", "price_per_share", "bidders", "proposals", "pct_bump", "days_proposal_to_signing", "first_bidder_won"],
    rows.map((r) => [
      r.targetDisplay,
      r.acquirerDisplay,
      BUYER_TYPE_LABELS[buyerType(r.slug, r.acquirerDisplay)],
      r.pricePlausible === false ? null : r.finalPrice,
      r.nBidders,
      r.nProposals,
      r.pctBump,
      r.daysFirstProposalToSigning,
      r.firstBidderWon === null ? null : r.firstBidderWon ? "yes" : "no",
    ])
  );

  return new NextResponse(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": 'attachment; filename="dealtrace-stats.csv"',
    },
  });
}
