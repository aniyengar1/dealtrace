import { formatPrice } from "@/lib/format";
import { acquireVerb } from "@/lib/labels";
import type { TickerDeal } from "@/lib/tickerDeals";

// Pure CSS marquee (no JS, no framer-motion) -- cheap enough to run
// forever in a hero that's already carrying a video loop, and respects
// prefers-reduced-motion for free via the global animation-duration
// override in globals.css. `deals` is a fixed curated list (see
// tickerDeals.ts), not a filter over the bulk-loaded set.
export function DealTicker({ deals }: { deals: TickerDeal[] }) {
  if (deals.length === 0) return null;

  const row = (keyPrefix: string) => (
    <div className="flex shrink-0 items-center gap-8 pr-8" aria-hidden={keyPrefix === "b"}>
      {deals.map((d) => (
        <span key={`${keyPrefix}-${d.slug}`} className="flex items-center gap-2 whitespace-nowrap text-sm text-ink-muted">
          <span className="text-ink">{d.acquirerDisplay}</span>
          <span>{acquireVerb(d.acquirerDisplay)}</span>
          <span className="text-ink">{d.targetDisplay}</span>
          <span className="font-mono text-accent tabular-nums">{formatPrice(d.finalPrice)}</span>
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
