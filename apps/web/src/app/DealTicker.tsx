import { formatPriceRange } from "@/lib/format";
import { acquirerDisplayName } from "@/lib/labels";
import type { DealSummary } from "@/lib/types";

// Pure CSS marquee (no JS, no framer-motion) -- cheap enough to run
// forever in a hero that's already carrying a video loop, and respects
// prefers-reduced-motion for free via the global animation-duration
// override in globals.css.
export function DealTicker({ deals }: { deals: DealSummary[] }) {
  const items = deals.filter((d) => d.n_facts_total > 0 && (d.final_price_low !== null || d.final_price_high !== null));
  if (items.length === 0) return null;

  const row = (keyPrefix: string) => (
    <div className="flex shrink-0 items-center gap-8 pr-8" aria-hidden={keyPrefix === "b"}>
      {items.map((d) => (
        <span key={`${keyPrefix}-${d.slug}`} className="flex items-center gap-2 whitespace-nowrap text-sm text-ink-muted">
          <span className="text-ink">{d.target}</span>
          <span className="text-ink-faint">&larr;</span>
          <span>{acquirerDisplayName(d.slug, d.acquirer)}</span>
          <span className="text-gold tabular-nums">{formatPriceRange(d.final_price_low, d.final_price_high)}</span>
        </span>
      ))}
    </div>
  );

  return (
    <div className="overflow-hidden">
      <div className="flex w-max animate-ticker motion-reduce:animate-none">
        {row("a")}
        {row("b")}
      </div>
    </div>
  );
}
