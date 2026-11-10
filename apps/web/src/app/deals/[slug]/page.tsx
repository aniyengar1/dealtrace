import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getDealBySlug,
  getLatestRunForDeal,
  getEventsForRun,
  getProposalsForRun,
  getValuationsForRun,
  getParagraphsForDeal,
} from "@/lib/queries";
import { formatDate, formatPriceRange } from "@/lib/format";
import { DealView } from "./DealView";

export const dynamic = "force-dynamic";

function pickFinalProposal<T extends { status: string; date_resolved: string | null; date_text: string }>(
  proposals: T[]
): T | null {
  const accepted = proposals.filter((p) => p.status === "accepted");
  const pool = accepted.length > 0 ? accepted : proposals;
  if (pool.length === 0) return null;
  return pool.reduce((latest, p) => {
    const latestKey = latest.date_resolved ?? latest.date_text;
    const pKey = p.date_resolved ?? p.date_text;
    return pKey > latestKey ? p : latest;
  });
}

export default async function DealPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const deal = await getDealBySlug(slug);
  if (!deal) notFound();

  const run = await getLatestRunForDeal(deal.id);
  if (!run) {
    return (
      <div>
        <h1 className="text-xl font-semibold">{deal.deal_name}</h1>
        <p className="mt-2 text-sm text-neutral-500">
          No extraction run has completed for this deal yet.
        </p>
      </div>
    );
  }

  const [events, proposals, valuations, paragraphs] = await Promise.all([
    getEventsForRun(run.id),
    getProposalsForRun(run.id),
    getValuationsForRun(run.id),
    getParagraphsForDeal(deal.id),
  ]);

  const finalProposal = pickFinalProposal(proposals);
  const finalPrice = finalProposal?.price_high ?? finalProposal?.price_low ?? null;
  const signingEvent = events.find((e) => e.event_type === "signing" && e.date_start);

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{deal.deal_name}</h1>
          <p className="mt-1 text-sm text-neutral-500">
            {deal.target} <span className="text-neutral-300">→</span> {deal.acquirer}
          </p>
        </div>
        <Link
          href={`/review/${deal.slug}`}
          className="rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-700"
        >
          Review facts
        </Link>
      </div>

      <dl className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-lg border border-neutral-200 bg-white p-3">
          <dt className="text-xs text-neutral-500">Price per share</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">
            {formatPriceRange(finalProposal?.price_low ?? null, finalProposal?.price_high ?? null)}
          </dd>
        </div>
        <div className="rounded-lg border border-neutral-200 bg-white p-3">
          <dt className="text-xs text-neutral-500">Signing date</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">
            {formatDate(signingEvent?.date_start ?? null)}
          </dd>
        </div>
        <div className="rounded-lg border border-neutral-200 bg-white p-3">
          <dt className="text-xs text-neutral-500">Proposals</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{proposals.length}</dd>
        </div>
        <div className="rounded-lg border border-neutral-200 bg-white p-3">
          <dt className="text-xs text-neutral-500">Events</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums">{events.length}</dd>
        </div>
      </dl>

      <div className="mt-8">
        <DealView
          target={deal.target}
          finalPrice={finalPrice}
          events={events}
          proposals={proposals}
          valuations={valuations}
          paragraphs={paragraphs}
        />
      </div>
    </div>
  );
}
