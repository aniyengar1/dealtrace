import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getDealBySlug,
  getLatestFactsRunForDeal,
  getLatestValuationsRunForDeal,
  getEventsForRun,
  getProposalsForRun,
  getValuationsForRun,
} from "@/lib/queries";
import { buildDealMemo, type MemoLine } from "@/lib/memo";
import { getDealMetricsBySlug } from "@/lib/dealMetrics";
import { dealTitle } from "@/lib/labels";
import { Container } from "@/components/ui/Container";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Deal memo",
};

function Citation({ slug, factId }: { slug: string; factId: string | null }) {
  if (!factId) return null;
  return (
    <Link href={`/deals/${slug}?fact=${factId}`} className="ml-1 text-xs text-accent hover:underline">
      [source]
    </Link>
  );
}

function LineList({ slug, lines }: { slug: string; lines: MemoLine[] }) {
  return (
    <ul className="list-disc space-y-1.5 pl-5 text-sm">
      {lines.map((l, i) => (
        <li key={i}>
          {l.text}
          <Citation slug={slug} factId={l.factId} />
        </li>
      ))}
    </ul>
  );
}

export default async function DealMemoPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const [deal, metrics] = await Promise.all([getDealBySlug(slug), getDealMetricsBySlug(slug)]);
  // Defense-in-depth -- see deals/[slug]/page.tsx's identical check.
  if (!deal || deal.excluded_from_stats || !deal.has_completed_run) notFound();

  const [factsRun, valuationsRun] = await Promise.all([
    getLatestFactsRunForDeal(deal.id),
    getLatestValuationsRunForDeal(deal.id),
  ]);
  // has_completed_run being true already guarantees factsRun exists --
  // this is unreachable in practice, kept only so TypeScript knows
  // factsRun is non-null below.
  if (!factsRun) notFound();

  const [events, proposals, valuations] = await Promise.all([
    getEventsForRun(factsRun.id),
    getProposalsForRun(factsRun.id),
    valuationsRun ? getValuationsForRun(valuationsRun.id) : Promise.resolve([]),
  ]);

  const memo = buildDealMemo(deal, events, proposals, valuations);

  return (
    <Container wide className="py-10">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-serif text-2xl font-semibold tracking-tight text-ink">{memo.dealName} · Deal memo</h1>
          <p className="mt-1 text-sm text-ink-muted">
            {metrics ? dealTitle(metrics.acquirerDisplay, metrics.targetDisplay) : dealTitle(memo.acquirer, memo.target)}
          </p>
        </div>
        <div className="flex gap-2">
          <a
            href={`/deals/${slug}/memo/export`}
            download={`${slug}-memo.md`}
            className="rounded-md border border-border-strong bg-surface px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-raised"
          >
            Download Markdown
          </a>
          <Link
            href={`/deals/${slug}`}
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-accent-ink hover:bg-accent/90"
          >
            Back to deal
          </Link>
        </div>
      </div>

      <section className="mt-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Deal terms</h2>
        <div className="mt-2 rounded-lg border border-border bg-surface p-4">
          <LineList slug={slug} lines={memo.dealTerms} />
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Parties and advisors</h2>
        <div className="mt-2 rounded-lg border border-border bg-surface p-4">
          <LineList slug={slug} lines={memo.partiesAndAdvisors} />
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Process timeline</h2>
        <div className="mt-2 rounded-lg border border-border bg-surface p-4">
          <LineList slug={slug} lines={memo.timeline} />
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Bid history</h2>
        <div className="mt-2 overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-surface-raised text-xs uppercase tracking-wide text-ink-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Date</th>
                <th className="px-3 py-2 font-medium">Proposer</th>
                <th className="px-3 py-2 font-medium">Recipient</th>
                <th className="px-3 py-2 font-medium">Price</th>
                <th className="px-3 py-2 font-medium">Premium</th>
                <th className="px-3 py-2 font-medium">Kind</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {memo.bidHistory.map((r, i) => (
                <tr key={i}>
                  <td className="px-3 py-2">{r.dateLabel}</td>
                  <td className="px-3 py-2">{r.proposer}</td>
                  <td className="px-3 py-2">{r.recipient}</td>
                  <td className="px-3 py-2 tabular-nums">{r.priceLabel}</td>
                  <td className="px-3 py-2 tabular-nums">{r.premiumLabel}</td>
                  <td className="px-3 py-2">{r.kindLabel}</td>
                  <td className="px-3 py-2">{r.statusLabel}</td>
                  <td className="px-3 py-2">
                    <Citation slug={slug} factId={r.factId} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Valuation summary</h2>
        <div className="mt-2 overflow-x-auto rounded-lg border border-border bg-surface">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border bg-surface-raised text-xs uppercase tracking-wide text-ink-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Advisor</th>
                <th className="px-3 py-2 font-medium">Method</th>
                <th className="px-3 py-2 font-medium">Implied range</th>
                <th className="px-3 py-2 font-medium">vs. final price</th>
                <th className="px-3 py-2 font-medium">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {memo.valuationSummary.map((r, i) => (
                <tr key={i}>
                  <td className="px-3 py-2">{r.advisor}</td>
                  <td className="px-3 py-2">{r.methodLabel}</td>
                  <td className="px-3 py-2 tabular-nums">{r.impliedRangeLabel}</td>
                  <td className="px-3 py-2 capitalize">{r.vsFinal}</td>
                  <td className="px-3 py-2">
                    <Citation slug={slug} factId={r.factId} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Notable features</h2>
        <div className="mt-2 rounded-lg border border-border bg-surface p-4">
          <LineList slug={slug} lines={memo.notableFeatures} />
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Talking points</h2>
        <div className="mt-2 rounded-lg border border-border bg-surface p-4">
          <LineList slug={slug} lines={memo.talkingPoints} />
        </div>
      </section>
    </Container>
  );
}
