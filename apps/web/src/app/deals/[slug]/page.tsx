import { notFound } from "next/navigation";
import type { Metadata } from "next";
import {
  getDealBySlug,
  getLatestFactsRunForDeal,
  getLatestValuationsRunForDeal,
  getEventsForRun,
  getProposalsForRun,
  getValuationsForRun,
  getParagraphsForDeal,
  getFilingUrlForDeal,
} from "@/lib/queries";
import { formatDate, formatPrice, formatPriceRange } from "@/lib/format";
import { acquirerDisplayName } from "@/lib/labels";
import { computeDealSummary } from "@/lib/dealSummary";
import { Container } from "@/components/ui/Container";
import { Card } from "@/components/ui/Card";
import { LinkButton } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { DealView } from "./DealView";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const deal = await getDealBySlug(slug);
  if (!deal) return {};
  return {
    title: `${deal.target} → ${acquirerDisplayName(deal.slug, deal.acquirer)}`,
    description: `Sourced sale-process timeline, bid history, and valuation analysis for ${deal.deal_name}, extracted from its SEC merger-proxy filing.`,
  };
}

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
      <Container wide className="py-10">
        <h1 className="font-serif text-2xl font-semibold text-ink">{deal.deal_name}</h1>
        <div className="mt-6">
          <EmptyState title="Not extracted yet" description="No completed extraction run exists for this deal yet." />
        </div>
      </Container>
    );
  }

  const [events, proposals, valuations, paragraphs, filingUrl] = await Promise.all([
    getEventsForRun(factsRun.id),
    getProposalsForRun(factsRun.id),
    valuationsRun ? getValuationsForRun(valuationsRun.id) : Promise.resolve([]),
    getParagraphsForDeal(deal.id),
    getFilingUrlForDeal(deal.search_term),
  ]);

  const finalProposal = pickFinalProposal(proposals);
  const finalPrice = finalProposal?.price_high ?? finalProposal?.price_low ?? null;
  const signingEvent = events.find((e) => e.event_type === "signing" && e.date_start);
  const summary = computeDealSummary(events, proposals, deal.target);
  const initialFact = factId
    ? [...events, ...proposals, ...valuations].find((f) => f.id === factId) ?? null
    : null;

  return (
    <Container wide className="py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            {deal.target} <span className="text-ink-faint">→</span>{" "}
            {acquirerDisplayName(deal.slug, deal.acquirer)}
          </h1>
          <p className="mt-1.5 text-sm text-ink-muted">{deal.deal_name}</p>
        </div>
        <div className="flex gap-2">
          <LinkButton href={`/deals/${deal.slug}/memo`} variant="secondary">
            Memo
          </LinkButton>
          <LinkButton href={`/review/${deal.slug}`} variant="primary">
            Review facts
          </LinkButton>
        </div>
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-3.5">
          <dt className="text-xs text-ink-muted">Price per share</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums text-accent">
            {formatPriceRange(finalProposal?.price_low ?? null, finalProposal?.price_high ?? null)}
          </dd>
        </Card>
        <Card className="p-3.5">
          <dt className="text-xs text-ink-muted">Signing date</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink">
            {formatDate(signingEvent?.date_start ?? null)}
          </dd>
        </Card>
        <Card className="p-3.5">
          <dt className="text-xs text-ink-muted">Proposals</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink">{proposals.length}</dd>
        </Card>
        <Card className="p-3.5">
          <dt className="text-xs text-ink-muted">Events</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink">{events.length}</dd>
        </Card>
      </dl>

      {filingUrl && (
        <p className="mt-3 text-sm">
          <a href={filingUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">
            View the SEC filing on EDGAR →
          </a>
        </p>
      )}

      <Card className="mt-6 p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Deal summary</h2>
        <dl className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-5">
          <div>
            <dt className="text-xs text-ink-muted">First bid → final</dt>
            <dd className="mt-0.5 text-sm font-medium tabular-nums text-ink">
              {(summary.firstBidPriceLow !== null || summary.firstBidPriceHigh !== null) &&
              summary.finalBidPrice !== null ? (
                <>
                  {formatPriceRange(summary.firstBidPriceLow, summary.firstBidPriceHigh)} →{" "}
                  {formatPrice(summary.finalBidPrice)}{" "}
                  <span className={summary.pctChange !== null && summary.pctChange >= 0 ? "text-positive" : "text-negative"}>
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
            <dt className="text-xs text-ink-muted">Rounds</dt>
            <dd className="mt-0.5 text-sm font-medium tabular-nums text-ink">{summary.nRounds}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Bidders</dt>
            <dd className="mt-0.5 text-sm font-medium tabular-nums text-ink">{summary.nBidders}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">First contact → signing</dt>
            <dd className="mt-0.5 text-sm font-medium tabular-nums text-ink">
              {summary.daysFirstContactToSigning !== null ? `${summary.daysFirstContactToSigning} days` : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Market check</dt>
            <dd className="mt-0.5 text-sm font-medium capitalize text-ink">{summary.marketCheck}</dd>
          </div>
        </dl>
        <p className="mt-3 text-xs text-ink-faint">
          Based on {summary.nConfirmed} confirmed and {summary.nUnreviewed} unreviewed fact
          {summary.nConfirmed + summary.nUnreviewed === 1 ? "" : "s"}
          {summary.nRejectedExcluded > 0 && ` (${summary.nRejectedExcluded} rejected fact${summary.nRejectedExcluded === 1 ? "" : "s"} excluded)`}.
        </p>
      </Card>

      <div className="mt-10">
        <DealView
          target={deal.target}
          acquirer={acquirerDisplayName(deal.slug, deal.acquirer)}
          finalPrice={finalPrice}
          events={events}
          proposals={proposals}
          valuations={valuations}
          paragraphs={paragraphs}
          initialFact={initialFact}
        />
      </div>
    </Container>
  );
}
