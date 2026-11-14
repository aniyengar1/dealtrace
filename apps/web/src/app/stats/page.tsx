import Link from "next/link";
import type { ReactNode } from "react";
import {
  listDeals,
  getLatestFactsRunForDeal,
  getEventsForRun,
  getProposalsForRun,
} from "@/lib/queries";
import { computeDealStatsRow, computeCrossDealSummary, type DealStatsRow } from "@/lib/crossDealStats";
import { acquirerDisplayName, BUYER_TYPE_LABELS } from "@/lib/labels";
import { formatPriceRange, formatPrice, formatPct } from "@/lib/format";
import { Container } from "@/components/ui/Container";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Cross-deal stats",
  description: "Early, small-sample aggregate findings across every deal with a completed extraction.",
};

// Every row here is built from a deal's latest (locked) facts run only --
// the same run getLatestFactsRunForDeal resolves on the deal page itself
// -- never a mix of several historical runs for the same deal.
async function loadRows(): Promise<DealStatsRow[]> {
  const deals = await listDeals();
  const rows: DealStatsRow[] = [];
  for (const deal of deals) {
    const run = await getLatestFactsRunForDeal(deal.id);
    if (!run) continue;
    const [events, proposals] = await Promise.all([getEventsForRun(run.id), getProposalsForRun(run.id)]);
    const row = computeDealStatsRow(deal, events, proposals);
    if (row) rows.push(row);
  }
  return rows;
}

function UnreviewedMark({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <sup className="ml-0.5 text-gold" title="Includes at least one unreviewed fact">
      •
    </sup>
  );
}

function Cell({
  href,
  unreviewed,
  children,
}: {
  href: string | null;
  unreviewed: boolean;
  children: ReactNode;
}) {
  const content = (
    <>
      {children}
      <UnreviewedMark show={unreviewed} />
    </>
  );
  if (!href) return <span>{content}</span>;
  return (
    <Link href={href} className="hover:underline">
      {content}
    </Link>
  );
}

function pctChangeLabel(row: DealStatsRow): string {
  if (row.pctChange === null) return "—";
  const sign = row.pctChange >= 0 ? "+" : "";
  const basis = row.pctChangeBasis ? ` (${row.pctChangeBasis} end)` : "";
  return `${sign}${row.pctChange.toFixed(1)}%${basis}`;
}

function GroupStatsCard({ label, stats }: { label: string; stats: { n: number; medianPctChange: number | null; meanPctChange: number | null; medianRounds: number | null; medianDaysToSigning: number | null } }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">{label}</h3>
        <span className="text-xs text-ink-muted">n = {stats.n} deal{stats.n === 1 ? "" : "s"}</span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-ink-muted">Median bump</dt>
          <dd className="tabular-nums">{formatPct(stats.medianPctChange)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Mean bump</dt>
          <dd className="tabular-nums">{formatPct(stats.meanPctChange)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Median rounds</dt>
          <dd className="tabular-nums">{stats.medianRounds ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Median days to signing</dt>
          <dd className="tabular-nums">{stats.medianDaysToSigning ?? "—"}</dd>
        </div>
      </dl>
    </div>
  );
}

export default async function StatsPage() {
  const rows = await loadRows();
  const summary = computeCrossDealSummary(rows);

  return (
    <Container wide className="py-10">
      <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink">Cross-deal findings</h1>
      <p className="mt-1 text-sm text-ink-muted">
        n = {summary.nDeals} deal{summary.nDeals === 1 ? "" : "s"} —{" "}
        <span className="font-medium text-gold">early / small-sample findings</span>, not a statistically
        reliable base rate. Every figure is read from each deal&apos;s latest locked extraction run only; cells
        marked <span className="text-gold">•</span> include at least one unreviewed fact.
      </p>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <GroupStatsCard label="All deals" stats={summary.overall} />
        <GroupStatsCard label={BUYER_TYPE_LABELS.strategic} stats={summary.byBuyerType.strategic} />
        <GroupStatsCard label={BUYER_TYPE_LABELS.sponsor} stats={summary.byBuyerType.sponsor} />
      </div>

      <div className="mt-8 overflow-x-auto rounded-lg border border-border bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-surface-raised text-xs uppercase tracking-wide text-ink-muted">
            <tr>
              <th className="px-3 py-2.5 font-medium">Target</th>
              <th className="px-3 py-2.5 font-medium">Acquirer</th>
              <th className="px-3 py-2.5 font-medium">Buyer type</th>
              <th className="px-3 py-2.5 font-medium">First bid → final</th>
              <th className="px-3 py-2.5 font-medium">Rounds</th>
              <th className="px-3 py-2.5 font-medium">Bidders</th>
              <th className="px-3 py-2.5 font-medium">Counters</th>
              <th className="px-3 py-2.5 font-medium">Days to signing</th>
              <th className="px-3 py-2.5 font-medium">Market check</th>
              <th className="px-3 py-2.5 font-medium">Final premium</th>
              <th className="px-3 py-2.5 font-medium">Activist</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row) => (
              <tr key={row.slug} className="hover:bg-surface-raised">
                <td className="px-3 py-3 font-medium">
                  <Link href={`/deals/${row.slug}`} className="hover:underline">
                    {row.target}
                  </Link>
                </td>
                <td className="px-3 py-3 text-ink-muted">{acquirerDisplayName(row.slug, row.acquirer)}</td>
                <td className="px-3 py-3 text-ink-muted">{BUYER_TYPE_LABELS[row.buyerType]}</td>
                <td className="px-3 py-3 tabular-nums">
                  <Cell
                    href={`/deals/${row.slug}?fact=${row.finalBidFactId ?? row.firstBidFactId ?? ""}`}
                    unreviewed={row.bidStatsUnreviewed}
                  >
                    {formatPriceRange(row.firstBidPriceLow, row.firstBidPriceHigh)} →{" "}
                    {formatPrice(row.finalBidPrice)} ({pctChangeLabel(row)})
                  </Cell>
                </td>
                <td className="px-3 py-3 tabular-nums">
                  <Cell href={`/deals/${row.slug}#bids`} unreviewed={row.bidStatsUnreviewed}>
                    {row.nRounds}
                  </Cell>
                </td>
                <td className="px-3 py-3 tabular-nums">
                  <Cell href={`/deals/${row.slug}#bids`} unreviewed={row.bidStatsUnreviewed}>
                    {row.nBidders}
                  </Cell>
                </td>
                <td className="px-3 py-3 tabular-nums">
                  <Cell href={`/deals/${row.slug}#bids`} unreviewed={row.bidStatsUnreviewed}>
                    {row.nCounteroffers}
                  </Cell>
                </td>
                <td className="px-3 py-3 tabular-nums">
                  <Cell
                    href={row.signingFactId ? `/deals/${row.slug}?fact=${row.signingFactId}` : `/deals/${row.slug}#timeline`}
                    unreviewed={row.timelineUnreviewed}
                  >
                    {row.daysFirstContactToSigning ?? "—"}
                  </Cell>
                </td>
                <td className="px-3 py-3 capitalize">
                  <Cell
                    href={row.marketCheckFactId ? `/deals/${row.slug}?fact=${row.marketCheckFactId}` : `/deals/${row.slug}#bids`}
                    unreviewed={row.marketCheckUnreviewed}
                  >
                    {row.marketCheck}
                  </Cell>
                </td>
                <td className="px-3 py-3 tabular-nums">
                  <Cell
                    href={row.finalBidFactId ? `/deals/${row.slug}?fact=${row.finalBidFactId}` : `/deals/${row.slug}`}
                    unreviewed={row.bidStatsUnreviewed}
                  >
                    {formatPct(row.finalPremiumPct)}
                  </Cell>
                </td>
                <td className="px-3 py-3">
                  {row.hasActivist ? (
                    <Cell
                      href={row.activistFactId ? `/deals/${row.slug}?fact=${row.activistFactId}` : `/deals/${row.slug}#timeline`}
                      unreviewed={row.activistUnreviewed}
                    >
                      Yes
                    </Cell>
                  ) : (
                    "No"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Container>
  );
}
