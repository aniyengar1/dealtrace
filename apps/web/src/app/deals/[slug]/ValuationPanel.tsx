"use client";

import type { ValuationRow } from "@/lib/types";
import { formatPrice, formatMultipleRange } from "@/lib/format";
import { valuationMethodLabel } from "@/lib/labels";
import { ReviewStatusBadge, factRowClassName } from "@/components/StatusBadge";

// Shared with DealView, which needs to know this BEFORE deciding
// whether to render the "Valuation vs. final price" section's header
// and description at all -- the vast majority of deals (798 of 806)
// have no valuations row whatsoever (no fairness opinion extracted,
// not a rendering bug), so showing a whole section for a one-line
// "nothing to plot" message on nearly every deal page is the thing
// actually worth hiding, not just the chart body.
export function hasPlottableValuations(valuations: ValuationRow[]): boolean {
  return valuations.some((v) => v.implied_price_low !== null && v.implied_price_high !== null);
}

export function ValuationPanel({
  valuations,
  finalPrice,
  onInspect,
}: {
  valuations: ValuationRow[];
  finalPrice: number | null;
  onInspect: (v: ValuationRow) => void;
}) {
  const plottable = valuations.filter((v) => v.implied_price_low !== null && v.implied_price_high !== null);

  if (plottable.length === 0) {
    return <p className="text-sm text-ink-muted">No valuation ranges with implied prices to plot.</p>;
  }

  const lows = plottable.map((v) => v.implied_price_low as number);
  const highs = plottable.map((v) => v.implied_price_high as number);
  let min = Math.min(...lows);
  let max = Math.max(...highs);
  if (finalPrice !== null) {
    min = Math.min(min, finalPrice);
    max = Math.max(max, finalPrice);
  }
  const pad = (max - min) * 0.08 || max * 0.1 || 1;
  const domainMin = min - pad;
  const domainMax = max + pad;
  const toPct = (v: number) => ((v - domainMin) / (domainMax - domainMin)) * 100;

  return (
    <div>
      <div className="relative space-y-3 pt-2">
        {finalPrice !== null && (
          <div
            className="absolute top-0 bottom-0 w-px bg-positive"
            style={{ left: `${toPct(finalPrice)}%` }}
          >
            <span className="absolute -top-5 -translate-x-1/2 whitespace-nowrap text-xs font-medium text-positive">
              final {formatPrice(finalPrice)}
            </span>
          </div>
        )}
        {plottable.map((v) => {
          const left = toPct(v.implied_price_low as number);
          const width = toPct(v.implied_price_high as number) - left;
          return (
            <div
              key={v.id}
              onClick={() => onInspect(v)}
              className={factRowClassName("rounded px-2 py-2")}
            >
              <div className="mb-1 flex items-center justify-between text-xs">
                <span className="font-medium text-ink">
                  {v.advisor} · {valuationMethodLabel(v.method)}
                </span>
                <div className="flex items-center gap-2">
                  <span className="tabular-nums text-ink-muted">
                    {formatMultipleRange(v.multiple_low, v.multiple_high)}
                  </span>
                  <ReviewStatusBadge status={v.review_status} />
                </div>
              </div>
              <div className="relative h-3 rounded bg-surface-raised">
                <div
                  className={`absolute top-0 h-3 rounded ${v.review_status === "unreviewed" ? "opacity-50" : ""} bg-chart-1`}
                  style={{ left: `${left}%`, width: `${Math.max(width, 0.8)}%` }}
                />
              </div>
              <div className="mt-0.5 flex justify-between text-xs tabular-nums text-ink-muted">
                <span>{formatPrice(v.implied_price_low)}</span>
                <span>{formatPrice(v.implied_price_high)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
