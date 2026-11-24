import Link from "next/link";
import type { Metadata } from "next";
import { listCanonicalDealMetrics, filterAndSortDeals, availableYears } from "@/lib/dealMetrics";
import { CONSIDERATION_TYPE_LABELS, PRICE_BUCKET_LABELS, type SortKey, type PriceBucket } from "@/lib/dealLabels";
import { formatDate } from "@/lib/format";
import { PriceValue } from "@/components/ui/PriceValue";
import { Container } from "@/components/ui/Container";
import { EmptyState } from "@/components/ui/EmptyState";
import { FilterBar } from "./FilterBar";
import { SortableHeader } from "./SortableHeader";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Deal explorer",
  description: "Search and filter every public-company sale process DealTrace has extracted from SEC filings.",
};

const SORT_KEYS: SortKey[] = ["signingDate", "finalPrice", "nBidders", "nProposals", "pctChange"];

function isSortKey(value: string | undefined): value is SortKey {
  return !!value && (SORT_KEYS as string[]).includes(value);
}

const PRICE_BUCKET_KEYS = Object.keys(PRICE_BUCKET_LABELS) as PriceBucket[];

function isPriceBucket(value: string | undefined): value is PriceBucket {
  return !!value && (PRICE_BUCKET_KEYS as string[]).includes(value);
}

export default async function DealsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const allRows = await listCanonicalDealMetrics();
  const years = availableYears(allRows);

  const sort = isSortKey(sp.sort) ? sp.sort : "nProposals";
  const dir = sp.dir === "asc" ? "asc" : "desc";
  const page = sp.page ? parseInt(sp.page, 10) || 1 : 1;

  const { rows, total, totalPages } = filterAndSortDeals(allRows, {
    q: sp.q,
    year: sp.year,
    considerationType: sp.consideration,
    priceBucket: isPriceBucket(sp.price) ? sp.price : undefined,
    sort,
    dir,
    page,
  });

  function pageHref(targetPage: number): string {
    const params = new URLSearchParams(Object.entries(sp).filter(([, v]) => v !== undefined) as [string, string][]);
    params.set("page", String(targetPage));
    return `/deals?${params.toString()}`;
  }

  const exportParams = new URLSearchParams(
    Object.entries(sp).filter(([k, v]) => v !== undefined && k !== "page") as [string, string][]
  );

  return (
    <Container wide className="py-10">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink">Deal explorer</h1>
          <p className="mt-1.5 text-sm text-ink-muted">
            {total} of {allRows.length} deals.
          </p>
        </div>
        <a
          href={`/deals/export?${exportParams.toString()}`}
          className="rounded-md border border-border-strong px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-raised"
        >
          Download CSV
        </a>
      </div>

      <div className="mt-6">
        <FilterBar years={years} />
      </div>

      {rows.length === 0 ? (
        <div className="mt-8">
          <EmptyState title="No deals match these filters" description="Try clearing a filter or searching a different term." />
        </div>
      ) : (
        /* overflow-x-auto alone forces overflow-y to also compute as "auto" (the
           CSS overflow-x/y visible-coupling rule), which makes this div -- not
           the viewport -- the nearest scrolling ancestor for the thead's
           position:sticky, so a "top-[Npx]" offset meant to clear the page nav
           never actually sticks to the page at all; scrolling the page just
           carries the header away with everything else and a body row ends up
           looking like it's peeking above where the header used to be. Giving
           this div its own bounded height and explicit overflow-auto makes it
           the real, intentional scrolling container, so "sticky top-0" pins the
           header to the top of its own (correctly computed) scrollport instead. */
        <div className="mt-6 max-h-[70vh] overflow-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 z-10 border-b border-border bg-surface font-mono text-xs uppercase tracking-wide text-ink-muted">
              <tr>
                <th className="px-3 py-2.5 font-medium">Target</th>
                <th className="px-3 py-2.5 font-medium">Acquirer</th>
                <th className="px-3 py-2.5 font-medium">
                  <SortableHeader sortKey="signingDate" label="Signing date" currentSort={sort} currentDir={dir} searchParams={sp} />
                </th>
                <th className="px-3 py-2.5 font-medium">Consideration</th>
                <th className="px-3 py-2.5 text-right font-medium">
                  <SortableHeader sortKey="finalPrice" label="Price / share" currentSort={sort} currentDir={dir} searchParams={sp} align="right" />
                </th>
                <th className="px-3 py-2.5 text-right font-medium">
                  <SortableHeader sortKey="nBidders" label="Bidders" currentSort={sort} currentDir={dir} searchParams={sp} align="right" />
                </th>
                <th className="px-3 py-2.5 text-right font-medium">
                  <SortableHeader sortKey="nProposals" label="Proposals" currentSort={sort} currentDir={dir} searchParams={sp} align="right" />
                </th>
                <th className="px-3 py-2.5 text-right font-medium">
                  <SortableHeader sortKey="pctChange" label="1st → final" currentSort={sort} currentDir={dir} searchParams={sp} align="right" />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row) => (
                <tr key={row.slug} className="transition-colors hover:bg-surface-raised">
                  <td className="px-3 py-3 font-medium">
                    <Link href={`/deals/${row.slug}`} className="hover:text-accent">
                      {row.targetDisplay}
                    </Link>
                  </td>
                  <td className="px-3 py-3 text-ink-muted">{row.acquirerDisplay}</td>
                  <td className="px-3 py-3 tabular-nums text-ink-muted">{formatDate(row.signingDate)}</td>
                  <td className="px-3 py-3 text-ink-muted">
                    {row.considerationType ? CONSIDERATION_TYPE_LABELS[row.considerationType] ?? row.considerationType : "–"}
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums text-accent">
                    <PriceValue price={row.finalPrice} plausible={row.pricePlausible} finalPriceIsRatio={row.finalPriceIsRatio} />
                  </td>
                  <td className="px-3 py-3 text-right tabular-nums">{row.nBidders}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{row.nProposals}</td>
                  <td className="px-3 py-3 text-right tabular-nums">
                    {row.pctBump !== null ? `${row.pctBump >= 0 ? "+" : ""}${row.pctBump.toFixed(1)}%` : "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <nav className="mt-5 flex items-center justify-between text-sm text-ink-muted">
          <Link
            href={pageHref(Math.max(1, page - 1))}
            aria-disabled={page <= 1}
            className={page <= 1 ? "pointer-events-none opacity-40" : "hover:text-ink"}
          >
            ← Previous
          </Link>
          <span>
            Page {Math.min(page, totalPages)} of {totalPages}
          </span>
          <Link
            href={pageHref(Math.min(totalPages, page + 1))}
            aria-disabled={page >= totalPages}
            className={page >= totalPages ? "pointer-events-none opacity-40" : "hover:text-ink"}
          >
            Next →
          </Link>
        </nav>
      )}
    </Container>
  );
}
