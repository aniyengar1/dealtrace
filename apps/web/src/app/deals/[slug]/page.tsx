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
import { getDealMetricsBySlug } from "@/lib/dealMetrics";
import { formatDate, formatPrice, formatPriceRange, formatShareCount, formatCompactDollar } from "@/lib/format";
import { dealTitle } from "@/lib/labels";
import { computeDealSummary } from "@/lib/dealSummary";
import { PriceValue } from "@/components/ui/PriceValue";
import { Container } from "@/components/ui/Container";
import { Card } from "@/components/ui/Card";
import { LinkButton } from "@/components/ui/Button";
import { DealView } from "./DealView";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const [deal, metrics] = await Promise.all([getDealBySlug(slug), getDealMetricsBySlug(slug)]);
  if (!deal) return {};
  const title = metrics ? dealTitle(metrics.acquirerDisplay, metrics.targetDisplay) : deal.deal_name;
  return {
    title,
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
  const [deal, metrics] = await Promise.all([getDealBySlug(slug), getDealMetricsBySlug(slug)]);
  // proxy.ts already blocks a real request from getting this far for an
  // excluded or not-yet-extracted deal's slug -- this is defense-in-
  // depth only (e.g. a stale slug-map cache window).
  if (!deal || deal.excluded_from_stats || !deal.has_completed_run) notFound();

  const [factsRun, valuationsRun] = await Promise.all([
    getLatestFactsRunForDeal(deal.id),
    getLatestValuationsRunForDeal(deal.id),
  ]);
  // has_completed_run being true already guarantees factsRun exists --
  // this is unreachable in practice, kept only so TypeScript knows
  // factsRun is non-null below.
  if (!factsRun) notFound();

  const [events, proposals, valuations, paragraphs, filingUrl] = await Promise.all([
    getEventsForRun(factsRun.id),
    getProposalsForRun(factsRun.id),
    valuationsRun ? getValuationsForRun(valuationsRun.id) : Promise.resolve([]),
    getParagraphsForDeal(deal.id),
    getFilingUrlForDeal(deal.search_term),
  ]);

  const finalProposal = pickFinalProposal(proposals);
  const finalPrice = metrics?.finalPrice ?? finalProposal?.price_high ?? finalProposal?.price_low ?? null;
  // Only available from deal_metrics (see PriceValue) -- every
  // canonical deal has a row there, so this only falls back to the
  // (safe, dollar-price-assuming) default when metrics itself is
  // unexpectedly missing.
  const finalPriceIsRatio = metrics?.finalPriceIsRatio ?? null;
  const signingEvent = events.find((e) => e.event_type === "signing" && e.date_start);
  const summary = computeDealSummary(events, proposals, deal.target);
  const initialFact = factId
    ? [...events, ...proposals, ...valuations].find((f) => f.id === factId) ?? null
    : null;
  const targetDisplay = metrics?.targetDisplay ?? deal.target;
  const acquirerDisplay = metrics?.acquirerDisplay ?? deal.acquirer;
  const sharesOutstanding = metrics?.sharesOutstanding ?? null;
  // Only computed when finalPrice is a genuine dollar figure -- for a
  // stock/mixed deal finalPrice is a ratio (or has already failed the
  // plausibility check), and multiplying a ratio by a share count
  // isn't a dollar value at all. Omitted rather than shown wrong; see
  // PriceValue's own ratio-vs-dollar distinction.
  const impliedEquityValue =
    sharesOutstanding !== null && finalPrice !== null && !finalPriceIsRatio && metrics?.pricePlausible !== false
      ? finalPrice * sharesOutstanding
      : null;

  return (
    <Container wide className="py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink sm:text-4xl">
            {dealTitle(acquirerDisplay, targetDisplay)}
          </h1>
          <p className="mt-1.5 text-sm text-ink-muted">{deal.deal_name}</p>
        </div>
        <div className="flex gap-2">
          <LinkButton href={`/deals/${deal.slug}/memo`} variant="secondary">
            Memo
          </LinkButton>
        </div>
      </div>

      {metrics?.dataQualityFlag === "proposals_not_extracted" && (
        <p className="mt-3 rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink-muted">
          Proposal history could not be extracted from this filing.
        </p>
      )}

      <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-3.5">
          <dt className="text-xs text-ink-muted">{finalPriceIsRatio ? "Exchange ratio" : "Price per share"}</dt>
          <dd className="mt-0.5 text-lg font-semibold tabular-nums text-accent">
            <PriceValue price={finalPrice} plausible={metrics?.pricePlausible ?? null} finalPriceIsRatio={finalPriceIsRatio} />
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

      {(sharesOutstanding !== null || metrics?.aggregateValue !== null) && (
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {sharesOutstanding !== null && (
            <Card className="p-3.5" title={metrics?.sharesOutstandingQuote ?? undefined}>
              <dt className="text-xs text-ink-muted">Shares outstanding (record date)</dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink">{formatShareCount(sharesOutstanding)}</dd>
            </Card>
          )}
          {impliedEquityValue !== null && (
            <Card className="p-3.5">
              <dt className="text-xs text-ink-muted">Implied equity value</dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums text-accent">{formatCompactDollar(impliedEquityValue)}</dd>
              <p className="mt-0.5 text-[11px] text-ink-faint">price × shares outstanding</p>
            </Card>
          )}
          {metrics?.aggregateValue !== null && metrics?.aggregateValue !== undefined && (
            <Card className="p-3.5" title={metrics?.aggregateValueQuote ?? undefined}>
              <dt className="text-xs text-ink-muted">Aggregate value (as stated in filing)</dt>
              <dd className="mt-0.5 text-lg font-semibold tabular-nums text-ink">{formatCompactDollar(metrics.aggregateValue)}</dd>
            </Card>
          )}
        </dl>
      )}

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
            <dt className="text-xs text-ink-muted">First proposal → signing</dt>
            <dd className="mt-0.5 text-sm font-medium tabular-nums text-ink">
              {summary.daysFirstProposalToSigning !== null ? `${summary.daysFirstProposalToSigning} days` : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Market check</dt>
            <dd className="mt-0.5 text-sm font-medium capitalize text-ink">{summary.marketCheck}</dd>
          </div>
        </dl>
        <p className="mt-3 text-xs text-ink-faint">Every fact is machine-verified against a quote from the filing.</p>
      </Card>

      <div className="mt-10">
        <DealView
          target={targetDisplay}
          acquirer={acquirerDisplay}
          finalPrice={finalPrice}
          finalPriceIsRatio={finalPriceIsRatio}
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
