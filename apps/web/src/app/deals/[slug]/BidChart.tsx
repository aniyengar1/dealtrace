"use client";

import { useMemo, useState } from "react";
import type { EventRow, ProposalRow } from "@/lib/types";
import { formatDate, formatPrice } from "@/lib/format";
import { eventTypeLabel } from "@/lib/labels";
import { computeRounds, type PlottableProposal, type Round } from "@/lib/rounds";

const BIDDER_COLORS = ["#2563eb", "#7c3aed", "#d97706", "#059669", "#db2777", "#0891b2"];
const PANEL_WIDTH = 720;
const PANEL_HEIGHT = 220;
const MARGIN = { top: 16, right: 20, bottom: 32, left: 56 };

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
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
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const points = round.proposals;

  const dates = points.map((p) => p.date.getTime());
  const lows = points.map((p) => p.proposal.price_low ?? p.proposal.price_high!);
  const highs = points.map((p) => p.proposal.price_high ?? p.proposal.price_low!);
  const minDate = Math.min(...dates);
  const maxDate = Math.max(...dates);
  const minPrice = Math.min(...lows);
  const maxPrice = Math.max(...highs);
  const pricePad = (maxPrice - minPrice) * 0.15 || maxPrice * 0.1 || 1;
  const datePad = (maxDate - minDate) * 0.08 || 1000 * 60 * 60 * 24 * 3;

  const xScale = (t: number) =>
    MARGIN.left +
    ((t - (minDate - datePad)) / (maxDate - minDate + 2 * datePad)) *
      (PANEL_WIDTH - MARGIN.left - MARGIN.right);
  const yScale = (price: number) =>
    PANEL_HEIGHT -
    MARGIN.bottom -
    ((price - (minPrice - pricePad)) / (maxPrice - minPrice + 2 * pricePad)) *
      (PANEL_HEIGHT - MARGIN.top - MARGIN.bottom);

  const series = new Map<string, PlottableProposal[]>();
  for (const point of points) {
    const key = point.proposal.proposer;
    const existing = series.get(key) ?? [];
    existing.push(point);
    series.set(key, existing);
  }

  const yTicks = Array.from(new Set([minPrice, (minPrice + maxPrice) / 2, maxPrice]));
  const xTicks = minDate === maxDate ? [minDate] : [minDate, maxDate];

  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4">
      <div className="mb-2 text-xs font-medium text-neutral-500">
        Round {roundIndex + 1} · {formatDate(isoDate(new Date(minDate)))} – {formatDate(isoDate(new Date(maxDate)))}
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
              stroke="#e5e5e5"
              strokeWidth={1}
            />
            <text x={MARGIN.left - 8} y={yScale(price)} textAnchor="end" dominantBaseline="middle" fontSize={11} fill="#737373">
              {formatPrice(price)}
            </text>
          </g>
        ))}
        {xTicks.map((t) => (
          <text key={t} x={xScale(t)} y={PANEL_HEIGHT - 10} textAnchor="middle" fontSize={11} fill="#737373">
            {formatDate(isoDate(new Date(t)))}
          </text>
        ))}

        {Array.from(series.entries()).map(([proposer, pts]) => {
          const isTarget = proposer === target;
          const color = colorByBidder.get(proposer)!;
          const sorted = [...pts].sort((a, b) => a.date.getTime() - b.date.getTime());
          const linePath = sorted
            .map(
              (p, i) =>
                `${i === 0 ? "M" : "L"}${xScale(p.date.getTime())},${yScale(p.proposal.price_high ?? p.proposal.price_low!)}`
            )
            .join(" ");

          return (
            <g key={proposer}>
              {sorted.length > 1 && (
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
                const isRange = low !== null && high !== null && low !== high;
                const x = xScale(p.date.getTime());
                const y = yScale(high ?? low!);
                const isAccepted = p.proposal.id === acceptedId;
                const dimmed = p.proposal.review_status === "unreviewed" ? 0.5 : 1;

                return (
                  <g
                    key={p.proposal.id}
                    onClick={() => onInspect(p.proposal)}
                    onMouseEnter={() => setHoveredId(p.proposal.id)}
                    onMouseLeave={() => setHoveredId((id) => (id === p.proposal.id ? null : id))}
                    className="cursor-pointer"
                  >
                    {isRange ? (
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
                    {isAccepted && <circle cx={x} cy={y} r={9} fill="none" stroke="#16a34a" strokeWidth={2} />}
                    {hoveredId === p.proposal.id && (
                      <text x={x} y={y - 14} textAnchor="middle" fontSize={11} fill="#171717" fontWeight={500}>
                        {isRange ? `${formatPrice(low)}–${formatPrice(high)}` : formatPrice(high ?? low)} ·{" "}
                        {formatDate(isoDate(p.date))}
                      </text>
                    )}
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
  const { rounds, breaks } = useMemo(() => computeRounds(proposals, events), [proposals, events]);
  const allPlotted = useMemo(() => rounds.flatMap((r) => r.proposals), [rounds]);
  const unplottable = proposals.length - allPlotted.length;

  const bidders = useMemo(
    () => Array.from(new Set(allPlotted.map((p) => p.proposal.proposer))).filter((b) => b !== target),
    [allPlotted, target]
  );
  const colorByBidder = useMemo(() => {
    const map = new Map<string, string>(bidders.map((b, i) => [b, BIDDER_COLORS[i % BIDDER_COLORS.length]]));
    map.set(target, "#737373");
    return map;
  }, [bidders, target]);

  const accepted = allPlotted.find((p) => p.proposal.status === "accepted");

  if (rounds.length === 0) {
    return <p className="text-sm text-neutral-500">No proposals with both a resolvable date and price to chart.</p>;
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
            <div className="my-2 flex items-center gap-2 px-2 text-xs text-neutral-500">
              <div className="h-px flex-1 bg-neutral-200" />
              <span>
                {breaks[i].events.length > 0
                  ? breaks[i].events.map((e) => eventTypeLabel(e.event_type)).join(", ")
                  : `${Math.round(breaks[i].gapDays)}-day gap`}
              </span>
              <div className="h-px flex-1 bg-neutral-200" />
            </div>
          )}
        </div>
      ))}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-1 text-xs text-neutral-600">
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
            <span className="inline-block h-2.5 w-2.5 rounded-full border-2 border-green-600" />
            accepted
          </span>
        )}
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-3 bg-neutral-400" />
          range bid (low–high)
        </span>
      </div>
      {unplottable > 0 && (
        <p className="text-xs text-neutral-400">
          {unplottable} proposal{unplottable === 1 ? "" : "s"} not shown (no per-share price, e.g. premium-only
          offers) — see the timeline below.
        </p>
      )}
    </div>
  );
}
