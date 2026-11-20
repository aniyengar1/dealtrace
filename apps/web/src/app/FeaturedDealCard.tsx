import Link from "next/link";
import { formatDate } from "@/lib/format";
import { dealTitle } from "@/lib/labels";
import { PriceValue } from "@/components/ui/PriceValue";
import type { DealMetricsRow } from "@/lib/dealMetrics";

export function FeaturedDealCard({ deal }: { deal: DealMetricsRow }) {
  return (
    <Link
      href={`/deals/${deal.slug}`}
      className="group flex flex-col gap-2 rounded-lg border border-border bg-surface p-5 transition-[color,background-color,border-color,transform,box-shadow] duration-200 hover:-translate-y-1 hover:border-border-strong hover:bg-surface-raised hover:shadow-lg hover:shadow-black/20"
    >
      <p className="font-serif text-lg text-ink">{dealTitle(deal.acquirerDisplay, deal.targetDisplay)}</p>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm text-ink-muted">
        <PriceValue
          price={deal.finalPrice}
          plausible={deal.pricePlausible}
          finalPriceIsRatio={deal.finalPriceIsRatio}
          className="tabular-nums text-accent"
        />
        <span className="tabular-nums">{formatDate(deal.signingDate)}</span>
        <span className="tabular-nums">{deal.nProposals} proposals</span>
      </div>
      <span className="mt-2 text-sm text-ink-muted transition-colors group-hover:text-accent">View deal →</span>
    </Link>
  );
}
