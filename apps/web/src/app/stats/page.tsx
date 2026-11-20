import Link from "next/link";
import { listCanonicalDealMetrics, type DealMetricsRow } from "@/lib/dealMetrics";
import { buyerType, BUYER_TYPE_LABELS } from "@/lib/labels";
import { statDecimals } from "@/lib/format";
import { PriceValue } from "@/components/ui/PriceValue";
import { Container } from "@/components/ui/Container";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Cross-deal stats",
  description: "Aggregate findings across every included deal, computed once per bulk-load run.",
};

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

function mean(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

interface GroupStats {
  n: number;
  medianPctBump: number | null;
  meanPctBump: number | null;
  medianBidders: number | null;
  // Anchored to the first PROPOSAL, not first contact -- a round-3
  // spot-check found first-contact dates the least reliable extracted
  // field (5 of 9 field errors), so that metric is excluded from
  // public stats entirely. See src.bulk_stats.compute_all().
  medianDaysProposalToSigning: number | null;
}

function groupStats(rows: DealMetricsRow[]): GroupStats {
  const bump = rows.map((r) => r.pctBump).filter((v): v is number => v !== null);
  return {
    n: rows.length,
    medianPctBump: median(bump),
    meanPctBump: mean(bump),
    medianBidders: median(rows.map((r) => r.nBidders)),
    medianDaysProposalToSigning: median(
      rows.map((r) => r.daysFirstProposalToSigning).filter((v): v is number => v !== null)
    ),
  };
}

function pctLabel(value: number | null): string {
  if (value === null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(statDecimals(value))}%`;
}

const PAGE_SIZE = 25;

function GroupStatsCard({ label, stats }: { label: string; stats: GroupStats }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">{label}</h3>
        <span className="text-xs text-ink-muted">n = {stats.n} deal{stats.n === 1 ? "" : "s"}</span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-ink-muted">Median bump</dt>
          <dd className="tabular-nums">{pctLabel(stats.medianPctBump)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Mean bump</dt>
          <dd className="tabular-nums">{pctLabel(stats.meanPctBump)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Median bidders</dt>
          <dd className="tabular-nums">{stats.medianBidders ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink-muted">Median days, proposal to signing</dt>
          <dd className="tabular-nums">
            {stats.medianDaysProposalToSigning !== null ? Math.round(stats.medianDaysProposalToSigning) : "—"}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export default async function StatsPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  // One query, no per-deal fan-out: deal_metrics already carries the
  // bidder/proposal/bump/days figures this page used to recompute from
  // raw events and proposals on every request.
  const rows = await listCanonicalDealMetrics();

  // The group-stats card above summarizes every included deal;
  // only the per-deal table below is paginated -- a single response
  // rendering every row as its own <tr> is the thing that was actually
  // slow, not the deal_metrics query itself.
  const sp = await searchParams;
  const page = Math.max(1, sp.page ? parseInt(sp.page, 10) || 1 : 1);
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageRows = rows.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  return (
    <Container wide className="py-10">
      <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink">Cross-deal findings</h1>
      <p className="mt-1 text-sm text-ink-muted">
        n = {rows.length} included deal{rows.length === 1 ? "" : "s"} — every figure is read from{" "}
        <code className="text-ink">deal_metrics</code>, computed once per bulk-load run.
      </p>

      <div className="mt-6 max-w-sm">
        <GroupStatsCard label="All deals" stats={groupStats(rows)} />
      </div>

      <div className="mt-8 overflow-x-auto rounded-lg border border-border bg-surface">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-surface-raised text-xs uppercase tracking-wide text-ink-muted">
            <tr>
              <th className="px-3 py-2.5 font-medium">Target</th>
              <th className="px-3 py-2.5 font-medium">Acquirer</th>
              <th className="px-3 py-2.5 font-medium">Buyer type</th>
              <th className="px-3 py-2.5 text-right font-medium">Price / share</th>
              <th className="px-3 py-2.5 text-right font-medium">Bidders</th>
              <th className="px-3 py-2.5 text-right font-medium">Proposals</th>
              <th className="px-3 py-2.5 text-right font-medium">1st → final</th>
              <th className="px-3 py-2.5 text-right font-medium">Days, proposal to signing</th>
              <th className="px-3 py-2.5">First bidder won</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {pageRows.map((row) => (
              <tr key={row.slug} className="hover:bg-surface-raised">
                <td className="px-3 py-3 font-medium">
                  <Link href={`/deals/${row.slug}`} className="hover:underline">
                    {row.targetDisplay}
                  </Link>
                </td>
                <td className="px-3 py-3 text-ink-muted">{row.acquirerDisplay}</td>
                <td className="px-3 py-3 text-ink-muted">
                  {BUYER_TYPE_LABELS[buyerType(row.slug, row.acquirerDisplay)]}
                </td>
                <td className="px-3 py-3 text-right tabular-nums">
                  <PriceValue price={row.finalPrice} plausible={row.pricePlausible} finalPriceIsRatio={row.finalPriceIsRatio} />
                </td>
                <td className="px-3 py-3 text-right tabular-nums">{row.nBidders}</td>
                <td className="px-3 py-3 text-right tabular-nums">{row.nProposals}</td>
                <td className="px-3 py-3 text-right tabular-nums">{pctLabel(row.pctBump)}</td>
                <td className="px-3 py-3 text-right tabular-nums">{row.daysFirstProposalToSigning ?? "—"}</td>
                <td className="px-3 py-3 text-ink-muted">
                  {row.firstBidderWon === null ? "—" : row.firstBidderWon ? "Yes" : "No"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <nav className="mt-5 flex items-center justify-between text-sm text-ink-muted">
          <Link
            href={`/stats?page=${Math.max(1, currentPage - 1)}`}
            aria-disabled={currentPage <= 1}
            className={currentPage <= 1 ? "pointer-events-none opacity-40" : "hover:text-ink"}
          >
            ← Previous
          </Link>
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <Link
            href={`/stats?page=${Math.min(totalPages, currentPage + 1)}`}
            aria-disabled={currentPage >= totalPages}
            className={currentPage >= totalPages ? "pointer-events-none opacity-40" : "hover:text-ink"}
          >
            Next →
          </Link>
        </nav>
      )}
    </Container>
  );
}
