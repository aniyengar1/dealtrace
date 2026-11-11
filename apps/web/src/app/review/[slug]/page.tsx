import Link from "next/link";
import { notFound } from "next/navigation";
import { requireReviewer } from "@/lib/auth";
import { getAllFactsForDeal, getDealBySlug, getLatestFactsRunForDeal, getParagraphsForDeal } from "@/lib/queries";
import { ReviewQueue } from "./ReviewQueue";

export const dynamic = "force-dynamic";

export default async function ReviewPage({ params }: { params: Promise<{ slug: string }> }) {
  await requireReviewer();

  const { slug } = await params;
  const deal = await getDealBySlug(slug);
  if (!deal) notFound();

  const factsRun = await getLatestFactsRunForDeal(deal.id);
  if (!factsRun) {
    return (
      <div>
        <h1 className="text-xl font-semibold">{deal.deal_name}</h1>
        <p className="mt-2 text-sm text-neutral-500">No extraction run to review yet.</p>
      </div>
    );
  }

  const [facts, paragraphs] = await Promise.all([
    getAllFactsForDeal(deal.id),
    getParagraphsForDeal(deal.id),
  ]);

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Review: {deal.deal_name}</h1>
          <p className="mt-1 text-sm text-neutral-500">{facts.length} extracted facts</p>
        </div>
        <Link href={`/deals/${deal.slug}`} className="text-sm text-neutral-500 hover:underline">
          ← back to deal
        </Link>
      </div>

      <div className="mt-6">
        <ReviewQueue slug={slug} initialFacts={facts} paragraphs={paragraphs} />
      </div>
    </div>
  );
}
