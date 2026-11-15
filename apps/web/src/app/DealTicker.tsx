import { formatPriceRange } from "@/lib/format";
import { acquirerDisplayName } from "@/lib/labels";
import type { DealSummary } from "@/lib/types";

// Pure CSS marquee (no JS, no framer-motion) -- cheap enough to run
// forever in a hero that's already carrying a video loop, and respects
// prefers-reduced-motion for free via the global animation-duration
// override in globals.css. `deals` is expected pre-filtered (see
// selectTickerDeals) -- canonical, real-acquirer deals only.
export function DealTicker({ deals }: { deals: DealSummary[] }) {
  if (deals.length === 0) return null;

  const row = (keyPrefix: string) => (
    <div className="flex shrink-0 items-center gap-8 pr-8" aria-hidden={keyPrefix === "b"}>
      {deals.map((d) => (
        <span key={`${keyPrefix}-${d.slug}`} className="flex items-center gap-2 whitespace-nowrap text-sm text-ink-muted">
          <span className="text-ink">{d.target}</span>
          <span className="text-ink-faint">&larr;</span>
          <span>{acquirerDisplayName(d.slug, d.acquirer)}</span>
          <span className="text-accent tabular-nums">{formatPriceRange(d.final_price_low, d.final_price_high)}</span>
        </span>
      ))}
    </div>
  );

  return (
    <div className="group overflow-hidden">
      <div className="flex w-max animate-ticker motion-reduce:animate-none">
        {row("a")}
        {row("b")}
      </div>
    </div>
  );
}
