import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { requireReviewer } from "@/lib/auth";
import { getAllFactsForDeal, getDealBySlug, getLatestFactsRunForDeal, getParagraphsForDeal } from "@/lib/queries";
import { Container } from "@/components/ui/Container";
import { EmptyState } from "@/components/ui/EmptyState";
import { ReviewQueue } from "./ReviewQueue";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Review",
};

export default async function ReviewPage({ params }: { params: Promise<{ slug: string }> }) {
  await requireReviewer();

  const { slug } = await params;
  const deal = await getDealBySlug(slug);
  if (!deal) notFound();

  const factsRun = await getLatestFactsRunForDeal(deal.id);
  if (!factsRun) {
    return (
      <Container wide className="py-10">
        <h1 className="font-serif text-2xl font-semibold text-ink">{deal.deal_name}</h1>
        <div className="mt-6">
          <EmptyState title="Nothing to review yet" description="No completed extraction run exists for this deal yet." />
        </div>
      </Container>
    );
  }

  const [facts, paragraphs] = await Promise.all([
    getAllFactsForDeal(deal.id),
    getParagraphsForDeal(deal.id),
  ]);

  return (
    <Container wide className="py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-serif text-2xl font-semibold tracking-tight text-ink">Review: {deal.deal_name}</h1>
          <p className="mt-1 text-sm text-ink-muted">{facts.length} extracted facts</p>
        </div>
        <Link href={`/deals/${deal.slug}`} className="text-sm text-ink-muted hover:underline">
          ← back to deal
        </Link>
      </div>

      <div className="mt-6">
        <ReviewQueue slug={slug} initialFacts={facts} paragraphs={paragraphs} />
      </div>
    </Container>
  );
}
