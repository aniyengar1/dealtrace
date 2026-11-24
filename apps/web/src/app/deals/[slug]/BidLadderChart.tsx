"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import type { EventRow, ProposalRow } from "@/lib/types";
import { formatDate, formatPrice, formatMultiple } from "@/lib/format";
import { computeRounds, type PlottableProposal } from "@/lib/rounds";
import { usePrefersReducedMotion } from "@/lib/useReducedMotion";

const BIDDER_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
  "var(--color-chart-6)",
];
const MARGIN = { top: 16, right: 150, bottom: 32, left: 56 };
// One fixed-height panel, not N stacked per-round panels -- a deal with
// six rounds used to mean six full-width charts; this is "sensible" for
// two points or twenty because the height never depends on round count,
// only on how many ticks the price axis needs.
const PANEL_WIDTH = 760;
const PANEL_HEIGHT = 280;

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function truncate(name: string, max = 20): string {
  return name.length > max ? `${name.slice(0, max - 1)}…` : name;
}

// The single Y-position a range bid's connecting line/label/accepted
// -ring should use -- the midpoint of its low-high range, not the high
// end (which used to make the connecting line trace the TOP of every
// range instead of its center). The range itself is still drawn in
// full via its own explicit low/high tick marks (see isRange below);
// this only picks one point to anchor the line/label/ring to.
function representativePrice(p: ProposalRow): number {
  const { price_low, price_high } = p;
  if (price_low !== null && price_high !== null) return (price_low + price_high) / 2;
  return (price_high ?? price_low) as number;
}

function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) return [min];
  const rawStep = (max - min) / (count - 1);
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const normalized = rawStep / magnitude;
  let step: number;
  if (normalized < 1.5) step = magnitude;
  else if (normalized < 3) step = 2 * magnitude;
  else if (normalized < 7) step = 5 * magnitude;
  else step = 10 * magnitude;

  const niceMin = Math.floor(min / step) * step;
  const niceMax = Math.ceil(max / step) * step;
  const ticks: number[] = [];
  for (let v = niceMin; v <= niceMax + step * 0.001; v += step) {
    ticks.push(Math.round(v * 100) / 100);
  }
  return ticks;
}

export function BidChart({
  proposals,
  events,
  target,
  finalPrice,
  finalPriceIsRatio,
  onInspect,
}: {
  proposals: ProposalRow[];
  events: EventRow[];
  target: string;
  finalPrice?: number | null;
  finalPriceIsRatio?: boolean | null;
  onInspect?: (p: ProposalRow) => void;
}) {
  const prefersReducedMotion = usePrefersReducedMotion();
  const { rounds } = useMemo(() => computeRounds(proposals, events, target), [proposals, events, target]);
  const allPlotted = useMemo(() => rounds.flatMap((r) => r.proposals), [rounds]);
  const unplottable = proposals.length - allPlotted.length;

  const bidders = useMemo(
    () => Array.from(new Set(allPlotted.map((p) => p.proposal.proposer))).filter((b) => b !== target),
    [allPlotted, target]
  );
  const colorByBidder = useMemo(() => {
    const map = new Map<string, string>(bidders.map((b, i) => [b, BIDDER_COLORS[i % BIDDER_COLORS.length]]));
    map.set(target, "var(--color-ink-faint)");
    return map;
  }, [bidders, target]);

  const accepted = allPlotted.find((p) => p.proposal.status === "accepted");

  // x: one continuous calendar axis across every round, not a reset
  // per-round sequence index -- a 3-day flurry and a 3-month lull are
  // no longer visually identical.
  const dates = allPlotted.map((p) => p.date.getTime());
  const minDate = Math.min(...dates, Infinity);
  const maxDate = Math.max(...dates, -Infinity);
  const xSpan = Math.max(1, maxDate - minDate);
  const xScale = (t: number) => MARGIN.left + ((t - minDate) / xSpan) * (PANEL_WIDTH - MARGIN.left - MARGIN.right);

  // Evenly spaced date ticks, not one per data point -- a deal with a
  // dozen proposals bunched into a few weeks used to render a dozen
  // overlapping date labels. Thinned left-to-right so neighboring
  // labels never render closer than a label-width apart, regardless of
  // how many raw ticks were requested.
  const xTicks: number[] = [];
  if (rounds.length > 0) {
    const rawTickCount = Math.min(5, new Set(dates).size);
    for (let i = 0; i < rawTickCount; i++) {
      const candidate = minDate + (xSpan * i) / Math.max(1, rawTickCount - 1);
      const lastKept = xTicks[xTicks.length - 1];
      if (lastKept === undefined || xScale(candidate) - xScale(lastKept) > 72) xTicks.push(candidate);
    }
  }

  const lows = allPlotted.map((p) => p.proposal.price_low ?? p.proposal.price_high!);
  const highs = allPlotted.map((p) => p.proposal.price_high ?? p.proposal.price_low!);
  let dataMin = Math.min(...lows, Infinity);
  let dataMax = Math.max(...highs, -Infinity);
  if (finalPrice !== null && finalPrice !== undefined && !finalPriceIsRatio) {
    dataMin = Math.min(dataMin, finalPrice);
    dataMax = Math.max(dataMax, finalPrice);
  }
  const yTicks = rounds.length > 0 ? niceTicks(dataMin, dataMax) : [];
  const domainMin = yTicks[0] ?? 0;
  const domainMax = yTicks[yTicks.length - 1] ?? 1;
  const yScale = (price: number) =>
    PANEL_HEIGHT -
    MARGIN.bottom -
    ((price - domainMin) / (domainMax - domainMin || 1)) * (PANEL_HEIGHT - MARGIN.top - MARGIN.bottom);

  // Subtle alternating shaded bands, one per round, so a reader can see
  // where the process paused/restarted without the bands competing with
  // the bid lines themselves for attention.
  const roundBands = rounds.map((round, i) => {
    const roundDates = round.proposals.map((p) => p.date.getTime());
    const x0 = xScale(Math.min(...roundDates)) - 10;
    const x1 = xScale(Math.max(...roundDates)) + 10;
    return { i, x0: Math.max(MARGIN.left, x0), x1: Math.min(PANEL_WIDTH - MARGIN.right, x1) };
  });

  const series = new Map<string, PlottableProposal[]>();
  for (const point of allPlotted) {
    const key = point.proposal.proposer;
    const existing = series.get(key) ?? [];
    existing.push(point);
    series.set(key, existing);
  }

  // Direct end-of-line labels (OWID/Pudding style) instead of relying
  // solely on a legend. Anchored to a shared column at the chart's
  // right edge -- not each bidder's own last-point x -- because a wide
  // auction (several sponsors all bidding in the final week) puts
  // their last points at nearly the same x *and* y; decluttering only
  // vertically while leaving x where it falls still let neighboring
  // labels' text visually cross. A shared column turns the same
  // declutter pass into a clean vertical list every time.
  const labelX = PANEL_WIDTH - MARGIN.right + 8;
  const endLabels = Array.from(series.entries())
    .filter(([proposer]) => proposer !== target)
    .map(([proposer, pts]) => {
      const last = [...pts].sort((a, b) => a.date.getTime() - b.date.getTime())[pts.length - 1];
      return { proposer, y: yScale(representativePrice(last.proposal)), color: colorByBidder.get(proposer)! };
    })
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < endLabels.length; i++) {
    if (endLabels[i].y - endLabels[i - 1].y < 14) endLabels[i].y = endLabels[i - 1].y + 14;
  }

  const finalPriceLabel =
    finalPrice !== null && finalPrice !== undefined
      ? finalPriceIsRatio
        ? `signed ${formatMultiple(finalPrice)}`
        : `signed ${formatPrice(finalPrice)}`
      : null;

  const noMotion = { initial: {}, animate: {}, transition: { duration: 0 } };

  // Fewer than 2 plottable bids can't show a trend -- one point (or
  // none) is a degenerate axis, not a chart. allPlotted is already
  // restricted to proposals with both a usable price AND date (see
  // computeRounds's chartable filter), so this is the real "not enough
  // data" check, not just "zero dated proposals."
  if (allPlotted.length < 2) {
    return <p className="text-sm text-ink-muted">Not enough priced proposals in the filing to chart.</p>;
  }

  const tableRows = [...allPlotted].sort((a, b) => a.date.getTime() - b.date.getTime());

  return (
    <div className="space-y-2">
      {/* Screen-reader/non-visual table equivalent of the SVG above --
          the chart's own aria-label gives the gist, but a reader who
          can't see the plot still needs the actual bid-by-bid data. */}
      {/* table-fixed matters here, not just visually: sr-only's width:1px
          is a hint auto table layout can ignore once cell content wants
          more room, which otherwise widens this (visually clipped but
          still laid out) table past the real viewport on narrow screens
          and drags the whole page into horizontal scroll with it. */}
      <table className="sr-only table-fixed">
        <caption>Bid history for {target}</caption>
        <thead>
          <tr>
            <th>Bidder</th>
            <th>Date</th>
            <th>Price</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {tableRows.map((p) => (
            <tr key={p.proposal.id}>
              <td>{p.proposal.proposer}</td>
              <td>{formatDate(isoDate(p.date))}</td>
              <td>
                {p.proposal.price_low !== null && p.proposal.price_high !== null && p.proposal.price_low !== p.proposal.price_high
                  ? `${formatPrice(p.proposal.price_low)}–${formatPrice(p.proposal.price_high)}`
                  : formatPrice(p.proposal.price_high ?? p.proposal.price_low)}
              </td>
              <td>{p.proposal.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="overflow-x-auto rounded-lg border border-border bg-surface p-4">
        <svg
          viewBox={`0 0 ${PANEL_WIDTH} ${PANEL_HEIGHT}`}
          className="w-full"
          style={{ minWidth: PANEL_WIDTH * 0.7 }}
          role="img"
          aria-label={`Bid history for ${target}: price per share offered by each bidder over time`}
        >
          {roundBands.map((band) => (
            <rect
              key={band.i}
              x={band.x0}
              y={MARGIN.top}
              width={Math.max(0, band.x1 - band.x0)}
              height={PANEL_HEIGHT - MARGIN.top - MARGIN.bottom}
              fill={band.i % 2 === 0 ? "var(--color-surface-raised)" : "transparent"}
              opacity={0.5}
            />
          ))}

          {yTicks.map((price) => (
            <g key={price}>
              <line
                x1={MARGIN.left}
                x2={PANEL_WIDTH - MARGIN.right}
                y1={yScale(price)}
                y2={yScale(price)}
                stroke="var(--color-border)"
                strokeWidth={1}
              />
              <text x={MARGIN.left - 8} y={yScale(price)} textAnchor="end" dominantBaseline="middle" fontSize={11} className="font-mono" fill="var(--color-ink-muted)">
                {formatPrice(price)}
              </text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={t} x={xScale(t)} y={PANEL_HEIGHT - 10} textAnchor="middle" fontSize={10} className="font-mono" fill="var(--color-ink-muted)">
              {formatDate(isoDate(new Date(t)))}
            </text>
          ))}

          {finalPrice !== null && finalPrice !== undefined && !finalPriceIsRatio && (
            <g>
              <line
                x1={MARGIN.left}
                x2={PANEL_WIDTH - MARGIN.right}
                y1={yScale(finalPrice)}
                y2={yScale(finalPrice)}
                stroke="var(--color-positive)"
                strokeWidth={1.5}
                strokeDasharray="5 4"
              />
              {/* Left edge, not the right -- the right margin is
                  reserved for per-bidder end-of-line labels, and the
                  final point often lands right on this line. */}
              <text x={MARGIN.left + 6} y={yScale(finalPrice) - 6} fontSize={11} className="font-mono" fill="var(--color-positive)">
                {finalPriceLabel}
              </text>
            </g>
          )}

          {Array.from(series.entries()).map(([proposer, pts]) => {
            const isTarget = proposer === target;
            const color = colorByBidder.get(proposer)!;
            const sorted = [...pts].sort((a, b) => a.date.getTime() - b.date.getTime());
            const realBids = sorted.filter((p) => p.proposal.proposal_kind !== "suggested_valuation");
            const linePath = realBids
              .map((p, i) => `${i === 0 ? "M" : "L"}${xScale(p.date.getTime())},${yScale(representativePrice(p.proposal))}`)
              .join(" ");

            return (
              <g key={proposer}>
                {realBids.length > 1 && (
                  <motion.path
                    d={linePath}
                    fill="none"
                    stroke={color}
                    strokeWidth={1.5}
                    strokeDasharray={isTarget ? "4 3" : undefined}
                    {...(prefersReducedMotion
                      ? noMotion
                      : {
                          initial: { pathLength: 0, opacity: 0 },
                          animate: { pathLength: 1, opacity: 0.6 },
                          transition: { duration: 0.8, ease: "easeInOut" },
                        })}
                  />
                )}
                {sorted.map((p) => {
                  const low = p.proposal.price_low;
                  const high = p.proposal.price_high;
                  const isHedged = p.proposal.proposal_kind === "suggested_valuation";
                  const isRange = low !== null && high !== null && low !== high;
                  const x = xScale(p.date.getTime());
                  const y = yScale(representativePrice(p.proposal));
                  const isAccepted = p.proposal.id === accepted?.proposal.id;
                  const dimmed = p.proposal.review_status === "unreviewed" ? 0.6 : 1;
                  const quote = p.proposal.source_quotes[0];
                  const priceLabel = isHedged
                    ? `indicated up to ${formatPrice(high ?? low)}`
                    : isRange
                      ? `${formatPrice(low)}–${formatPrice(high)}`
                      : formatPrice(high ?? low);
                  const tooltip = [
                    `${proposer} — ${formatDate(isoDate(p.date))} — ${priceLabel}`,
                    quote ? `“${quote.length > 240 ? `${quote.slice(0, 240)}…` : quote}”` : null,
                  ]
                    .filter(Boolean)
                    .join("\n");

                  return (
                    <g
                      key={p.proposal.id}
                      onClick={() => onInspect?.(p.proposal)}
                      className={onInspect ? "cursor-pointer" : undefined}
                    >
                      <title>{tooltip}</title>
                      {isHedged ? (
                        <circle cx={x} cy={y} r={5} fill="var(--color-surface)" stroke={color} strokeWidth={2} opacity={dimmed} />
                      ) : isRange ? (
                        <>
                          <line x1={x} x2={x} y1={yScale(low!)} y2={yScale(high!)} stroke={color} strokeWidth={3} opacity={dimmed * 0.85} />
                          <line x1={x - 4} x2={x + 4} y1={yScale(low!)} y2={yScale(low!)} stroke={color} strokeWidth={2} opacity={dimmed} />
                          <line x1={x - 4} x2={x + 4} y1={yScale(high!)} y2={yScale(high!)} stroke={color} strokeWidth={2} opacity={dimmed} />
                        </>
                      ) : isTarget ? (
                        <rect x={x - 4} y={y - 4} width={8} height={8} fill={color} opacity={dimmed} />
                      ) : (
                        <circle cx={x} cy={y} r={4.5} fill={color} opacity={dimmed} />
                      )}
                      {isAccepted && <circle cx={x} cy={y} r={9} fill="none" stroke="var(--color-positive)" strokeWidth={2} />}
                    </g>
                  );
                })}
              </g>
            );
          })}

          {endLabels.map((l) => (
            <text key={l.proposer} x={labelX} y={l.y} dominantBaseline="middle" fontSize={11} fill={l.color}>
              {truncate(l.proposer)}
            </text>
          ))}
        </svg>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-1 text-xs text-ink-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2 w-2" style={{ backgroundColor: colorByBidder.get(target) }} />
          {target} (target counteroffers)
        </span>
        {accepted && (
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full border-2 border-positive" />
            accepted
          </span>
        )}
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-3 bg-ink-faint" />
          range bid (low–high)
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full border-2 border-border-strong bg-surface" />
          hedged / suggested valuation
        </span>
        {finalPriceLabel && (
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-3 border-t-2 border-dashed border-positive" />
            {finalPriceLabel}
          </span>
        )}
      </div>
      {unplottable > 0 && (
        <p className="text-xs text-ink-faint">
          {unplottable} proposal{unplottable === 1 ? "" : "s"} not shown (no usable price and date) — see the timeline below.
        </p>
      )}
    </div>
  );
}
