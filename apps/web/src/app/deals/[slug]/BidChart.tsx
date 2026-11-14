"use client";

import { useMemo } from "react";
import type { EventRow, ProposalRow } from "@/lib/types";
import { formatDate, formatPrice } from "@/lib/format";
import { eventTypeLabel } from "@/lib/labels";
import { computeRounds, type PlottableProposal, type Round } from "@/lib/rounds";

const BIDDER_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
  "var(--color-chart-6)",
];
const PANEL_WIDTH = 720;
const PANEL_HEIGHT = 240;
const MARGIN = { top: 16, right: 20, bottom: 32, left: 56 };

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

// Round, human-friendly axis ticks (e.g. 75/80/85, not whatever the exact
// min/mid/max of the data happens to be).
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

function RoundPanel({
  round,
  roundIndex,
  target,
  colorByBidder,
  acceptedId,
  onInspect,
}: {
  round: Round;
  roundIndex: number;
  target: string;
  colorByBidder: Map<string, string>;
  acceptedId: string | null;
  onInspect: (p: ProposalRow) => void;
}) {
  const points = round.proposals;

  // X-axis is sequence-based, not time-proportional -- a round with 5
  // bids over 3 days and one with 5 bids over 3 months both get evenly
  // spaced slots, so a dense cluster is just as readable as a sparse one.
  const uniqueDates = Array.from(new Set(points.map((p) => p.date.getTime()))).sort((a, b) => a - b);
  const xScale = (t: number) => {
    const idx = uniqueDates.indexOf(t);
    const denom = Math.max(uniqueDates.length - 1, 1);
    return MARGIN.left + (idx / denom) * (PANEL_WIDTH - MARGIN.left - MARGIN.right);
  };

  const lows = points.map((p) => p.proposal.price_low ?? p.proposal.price_high!);
  const highs = points.map((p) => p.proposal.price_high ?? p.proposal.price_low!);
  const dataMin = Math.min(...lows);
  const dataMax = Math.max(...highs);
  const yTicks = niceTicks(dataMin, dataMax);
  const domainMin = yTicks[0];
  const domainMax = yTicks[yTicks.length - 1];
  const yScale = (price: number) =>
    PANEL_HEIGHT -
    MARGIN.bottom -
    ((price - domainMin) / (domainMax - domainMin || 1)) * (PANEL_HEIGHT - MARGIN.top - MARGIN.bottom);

  const series = new Map<string, PlottableProposal[]>();
  for (const point of points) {
    const key = point.proposal.proposer;
    const existing = series.get(key) ?? [];
    existing.push(point);
    series.set(key, existing);
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="mb-2 text-xs font-medium text-ink-muted">
        Round {roundIndex + 1} · {formatDate(isoDate(points[0].date))} – {formatDate(isoDate(points[points.length - 1].date))}
      </div>
      <svg
        viewBox={`0 0 ${PANEL_WIDTH} ${PANEL_HEIGHT}`}
        className="w-full"
        role="img"
        aria-label={`Round ${roundIndex + 1} bids`}
      >
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
            <text x={MARGIN.left - 8} y={yScale(price)} textAnchor="end" dominantBaseline="middle" fontSize={11} fill="var(--color-ink-muted)">
              {formatPrice(price)}
            </text>
          </g>
        ))}
        {uniqueDates.map((t) => (
          <text key={t} x={xScale(t)} y={PANEL_HEIGHT - 10} textAnchor="middle" fontSize={11} fill="var(--color-ink-muted)">
            {formatDate(isoDate(new Date(t)))}
          </text>
        ))}

        {Array.from(series.entries()).map(([proposer, pts]) => {
          const isTarget = proposer === target;
          const color = colorByBidder.get(proposer)!;
          const sorted = [...pts].sort((a, b) => a.date.getTime() - b.date.getTime());
          const realBids = sorted.filter((p) => p.proposal.proposal_kind !== "suggested_valuation");
          const linePath = realBids
            .map(
              (p, i) =>
                `${i === 0 ? "M" : "L"}${xScale(p.date.getTime())},${yScale(p.proposal.price_high ?? p.proposal.price_low!)}`
            )
            .join(" ");

          return (
            <g key={proposer}>
              {realBids.length > 1 && (
                <path
                  d={linePath}
                  fill="none"
                  stroke={color}
                  strokeWidth={1.5}
                  strokeDasharray={isTarget ? "4 3" : undefined}
                  opacity={0.5}
                />
              )}
              {sorted.map((p) => {
                const low = p.proposal.price_low;
                const high = p.proposal.price_high;
                const isHedged = p.proposal.proposal_kind === "suggested_valuation";
                const isRange = low !== null && high !== null && low !== high;
                const x = xScale(p.date.getTime());
                const y = yScale(high ?? low!);
                const isAccepted = p.proposal.id === acceptedId;
                const dimmed = p.proposal.review_status === "unreviewed" ? 0.5 : 1;
                const priceLabel = isHedged
                  ? `indicated up to ${formatPrice(high ?? low)}`
                  : isRange
                    ? `${formatPrice(low)}–${formatPrice(high)}`
                    : formatPrice(high ?? low);

                return (
                  <g key={p.proposal.id} onClick={() => onInspect(p.proposal)} className="cursor-pointer">
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
                    <text x={x} y={y - 10} textAnchor="middle" fontSize={10} fill="var(--color-ink)">
                      {priceLabel}
                    </text>
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function BidChart({
  proposals,
  events,
  target,
  onInspect,
}: {
  proposals: ProposalRow[];
  events: EventRow[];
  target: string;
  onInspect: (p: ProposalRow) => void;
}) {
  const { rounds, breaks } = useMemo(() => computeRounds(proposals, events, target), [proposals, events, target]);
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

  if (rounds.length === 0) {
    return <p className="text-sm text-ink-muted">No proposals with both a resolvable date and price to chart.</p>;
  }

  return (
    <div className="space-y-2">
      {rounds.map((round, i) => (
        <div key={i}>
          <RoundPanel
            round={round}
            roundIndex={i}
            target={target}
            colorByBidder={colorByBidder}
            acceptedId={accepted?.proposal.id ?? null}
            onInspect={onInspect}
          />
          {breaks[i] && (
            <div className="my-2 flex items-center gap-2 px-2 text-xs text-ink-muted">
              <div className="h-px flex-1 bg-border" />
              <span>
                {breaks[i].events.length > 0
                  ? breaks[i].events.map((e) => eventTypeLabel(e.event_type)).join(", ")
                  : "process break"}
              </span>
              <div className="h-px flex-1 bg-border" />
            </div>
          )}
        </div>
      ))}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-1 text-xs text-ink-muted">
        {Array.from(colorByBidder.entries()).map(([bidder, color]) => (
          <span key={bidder} className="inline-flex items-center gap-1.5">
            {bidder === target ? (
              <span className="inline-block h-2 w-2" style={{ backgroundColor: color }} />
            ) : (
              <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
            )}
            {bidder}
            {bidder === target ? " (target counteroffers)" : ""}
          </span>
        ))}
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
      </div>
      {unplottable > 0 && (
        <p className="text-xs text-ink-faint">
          {unplottable} proposal{unplottable === 1 ? "" : "s"} not shown (no per-share price) — see the timeline below.
        </p>
      )}
    </div>
  );
}
