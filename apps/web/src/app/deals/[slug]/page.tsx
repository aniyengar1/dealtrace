import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getDealBySlug,
  getLatestFactsRunForDeal,
  getLatestValuationsRunForDeal,
  getEventsForRun,
  getProposalsForRun,
  getValuationsForRun,
  getParagraphsForDeal,
} from "@/lib/queries";
import { formatDate, formatPrice, formatPriceRange } from "@/lib/format";
import { acquirerDisplayName } from "@/lib/labels";
import { computeDealSummary } from "@/lib/dealSummary";
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

export default async function DealPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ fact?: string }>;
}) {
  const { slug } = await params;
  const { fact: factId } = await searchParams;
  const deal = await getDealBySlug(slug);
  if (!deal) notFound();

  const [factsRun, valuationsRun] = await Promise.all([
    getLatestFactsRunForDeal(deal.id),
    getLatestValuationsRunForDeal(deal.id),
  ]);
  if (!factsRun) {
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
    getEventsForRun(factsRun.id),
    getProposalsForRun(factsRun.id),
    valuationsRun ? getValuationsForRun(valuationsRun.id) : Promise.resolve([]),
    getParagraphsForDeal(deal.id),
  ]);

  const finalProposal = pickFinalProposal(proposals);
  const finalPrice = finalProposal?.price_high ?? finalProposal?.price_low ?? null;
  const signingEvent = events.find((e) => e.event_type === "signing" && e.date_start);
  const summary = computeDealSummary(events, proposals, deal.target);
  const initialFact = factId
    ? [...events, ...proposals, ...valuations].find((f) => f.id === factId) ?? null
    : null;

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{deal.deal_name}</h1>
          <p className="mt-1 text-sm text-neutral-500">
            {deal.target} <span className="text-neutral-300">→</span> {acquirerDisplayName(deal.slug, deal.acquirer)}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/deals/${deal.slug}/memo`}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50"
          >
            Memo
          </Link>
          <Link
            href={`/review/${deal.slug}`}
            className="rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-700"
          >
            Review facts
          </Link>
        </div>
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

      <div className="mt-6 rounded-lg border border-neutral-200 bg-white p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">Deal summary</h2>
        <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-5">
          <div>
            <dt className="text-xs text-neutral-500">First bid → final</dt>
            <dd className="mt-0.5 text-sm font-medium tabular-nums">
              {(summary.firstBidPriceLow !== null || summary.firstBidPriceHigh !== null) &&
              summary.finalBidPrice !== null ? (
                <>
                  {formatPriceRange(summary.firstBidPriceLow, summary.firstBidPriceHigh)} →{" "}
                  {formatPrice(summary.finalBidPrice)}{" "}
                  <span className={summary.pctChange !== null && summary.pctChange >= 0 ? "text-emerald-600" : "text-red-600"}>
                    ({summary.pctChange !== null ? `${summary.pctChange >= 0 ? "+" : ""}${summary.pctChange.toFixed(1)}%` : "—"}
                    {summary.pctChangeBasis ? ` from ${summary.pctChangeBasis}` : ""})
                  </span>
                </>
              ) : (
                "—"
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-neutral-500">Rounds</dt>
            <dd className="mt-0.5 text-sm font-medium tabular-nums">{summary.nRounds}</dd>
          </div>
          <div>
            <dt className="text-xs text-neutral-500">Bidders</dt>
            <dd className="mt-0.5 text-sm font-medium tabular-nums">{summary.nBidders}</dd>
          </div>
          <div>
            <dt className="text-xs text-neutral-500">First contact → signing</dt>
            <dd className="mt-0.5 text-sm font-medium tabular-nums">
              {summary.daysFirstContactToSigning !== null ? `${summary.daysFirstContactToSigning} days` : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-neutral-500">Market check</dt>
            <dd className="mt-0.5 text-sm font-medium capitalize">{summary.marketCheck}</dd>
          </div>
        </dl>
        <p className="mt-3 text-xs text-neutral-400">
          Based on {summary.nConfirmed} confirmed and {summary.nUnreviewed} unreviewed fact
          {summary.nConfirmed + summary.nUnreviewed === 1 ? "" : "s"}
          {summary.nRejectedExcluded > 0 && ` (${summary.nRejectedExcluded} rejected fact${summary.nRejectedExcluded === 1 ? "" : "s"} excluded)`}.
        </p>
      </div>

      <div className="mt-8">
        <DealView
          target={deal.target}
          finalPrice={finalPrice}
          events={events}
          proposals={proposals}
          valuations={valuations}
          paragraphs={paragraphs}
          initialFact={initialFact}
        />
      </div>
    </div>
  );
}
