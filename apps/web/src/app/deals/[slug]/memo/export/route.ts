import { NextResponse } from "next/server";
import {
  getDealBySlug,
  getLatestFactsRunForDeal,
  getLatestValuationsRunForDeal,
  getEventsForRun,
  getProposalsForRun,
  getValuationsForRun,
} from "@/lib/queries";
import { buildDealMemo, renderMemoMarkdown } from "@/lib/memo";

export const dynamic = "force-dynamic";

export async function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const deal = await getDealBySlug(slug);
  if (!deal || deal.excluded_from_stats) return new NextResponse("Not found", { status: 404 });

  const [factsRun, valuationsRun] = await Promise.all([
    getLatestFactsRunForDeal(deal.id),
    getLatestValuationsRunForDeal(deal.id),
  ]);
  if (!factsRun) return new NextResponse("No extraction run completed for this deal yet", { status: 404 });

  const [events, proposals, valuations] = await Promise.all([
    getEventsForRun(factsRun.id),
    getProposalsForRun(factsRun.id),
    valuationsRun ? getValuationsForRun(valuationsRun.id) : Promise.resolve([]),
  ]);

  const memo = buildDealMemo(deal, events, proposals, valuations);
  const markdown = renderMemoMarkdown(memo);

  return new NextResponse(markdown, {
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      "Content-Disposition": `attachment; filename="${slug}-memo.md"`,
    },
  });
}
