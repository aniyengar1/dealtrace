import Link from "next/link";
import { formatDate, formatPriceRange } from "@/lib/format";
import { acquirerDisplayName } from "@/lib/labels";
import type { DealSummary } from "@/lib/types";

export function FeaturedDealCard({ deal }: { deal: DealSummary }) {
  return (
    <Link
      href={`/deals/${deal.slug}`}
      className="group flex flex-col gap-2 rounded-lg border border-border bg-surface p-5 transition-[color,background-color,border-color,transform,box-shadow] duration-200 hover:-translate-y-1 hover:border-border-strong hover:bg-surface-raised hover:shadow-lg hover:shadow-black/20"
    >
      <p className="font-serif text-lg text-ink">
        {deal.target} <span className="text-ink-faint">→</span> {acquirerDisplayName(deal.slug, deal.acquirer)}
      </p>
      <div className="mt-1 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-sm text-ink-muted">
        <span className="tabular-nums text-accent">
          {formatPriceRange(deal.final_price_low, deal.final_price_high)}
        </span>
        <span className="tabular-nums">{formatDate(deal.signing_date)}</span>
        <span className="tabular-nums">{deal.n_proposals} proposals</span>
      </div>
      <span className="mt-2 text-sm text-ink-muted transition-colors group-hover:text-accent">View deal →</span>
    </Link>
  );
}
