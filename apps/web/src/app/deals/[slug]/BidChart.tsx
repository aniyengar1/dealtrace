"use client";

import { useMemo, useState } from "react";
import type { ProposalRow } from "@/lib/types";
import { parseFilingDate, formatDate, formatPrice } from "@/lib/format";

const BIDDER_COLORS = ["#2563eb", "#7c3aed", "#d97706", "#059669", "#db2777", "#0891b2"];
const WIDTH = 720;
const HEIGHT = 280;
const MARGIN = { top: 20, right: 20, bottom: 32, left: 56 };

interface PlottablePoint {
  proposal: ProposalRow;
  date: Date;
  price: number;
}

export function BidChart({
  proposals,
  target,
  onInspect,
}: {
  proposals: ProposalRow[];
  target: string;
  onInspect: (p: ProposalRow) => void;
}) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const points: PlottablePoint[] = useMemo(() => {
    return proposals
      .map((proposal) => {
        const date = parseFilingDate(proposal.date_text, proposal.date_resolved);
        const price = proposal.price_high ?? proposal.price_low;
        if (!date || price === null) return null;
        return { proposal, date, price };
      })
      .filter((p): p is PlottablePoint => p !== null);
  }, [proposals]);

  const unplottable = proposals.length - points.length;

  if (points.length === 0) {
    return (
      <p className="text-sm text-neutral-500">
        No proposals with both a resolvable date and price to chart.
      </p>
    );
  }

  const dates = points.map((p) => p.date.getTime());
  const prices = points.map((p) => p.price);
  const minDate = Math.min(...dates);
  const maxDate = Math.max(...dates);
  const minPrice = Math.min(...prices);
  const maxPrice = Math.max(...prices);
  const pricePad = (maxPrice - minPrice) * 0.12 || maxPrice * 0.1 || 1;
  const datePad = (maxDate - minDate) * 0.06 || 1000 * 60 * 60 * 24;

  const xScale = (t: number) =>
    MARGIN.left +
    ((t - (minDate - datePad)) / (maxDate - minDate + 2 * datePad)) * (WIDTH - MARGIN.left - MARGIN.right);
  const yScale = (price: number) =>
    HEIGHT -
    MARGIN.bottom -
    ((price - (minPrice - pricePad)) / (maxPrice - minPrice + 2 * pricePad)) *
      (HEIGHT - MARGIN.top - MARGIN.bottom);

  const bidders = Array.from(new Set(points.map((p) => p.proposal.proposer))).filter((b) => b !== target);
  const colorByBidder = new Map(bidders.map((b, i) => [b, BIDDER_COLORS[i % BIDDER_COLORS.length]]));
  colorByBidder.set(target, "#737373");

  const series = new Map<string, PlottablePoint[]>();
  for (const point of points) {
    const key = point.proposal.proposer;
    const existing = series.get(key) ?? [];
    existing.push(point);
    series.set(key, existing);
  }
  for (const pts of series.values()) pts.sort((a, b) => a.date.getTime() - b.date.getTime());

  const accepted = points.find((p) => p.proposal.status === "accepted");

  const yTicks = [minPrice, (minPrice + maxPrice) / 2, maxPrice];

  return (
    <div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full" role="img" aria-label="Bids over time">
        {yTicks.map((price) => (
          <g key={price}>
            <line
              x1={MARGIN.left}
              x2={WIDTH - MARGIN.right}
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

        {Array.from(series.entries()).map(([proposer, pts]) => {
          const isTarget = proposer === target;
          const color = colorByBidder.get(proposer)!;
          const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${xScale(p.date.getTime())},${yScale(p.price)}`).join(" ");
          return (
            <g key={proposer}>
              {pts.length > 1 && (
                <path d={path} fill="none" stroke={color} strokeWidth={1.5} strokeDasharray={isTarget ? "4 3" : undefined} opacity={0.6} />
              )}
              {pts.map((p) => {
                const isAccepted = p.proposal.id === accepted?.proposal.id;
                const x = xScale(p.date.getTime());
                const y = yScale(p.price);
                return (
                  <g
                    key={p.proposal.id}
                    onClick={() => onInspect(p.proposal)}
                    onMouseEnter={() => setHoveredId(p.proposal.id)}
                    onMouseLeave={() => setHoveredId((id) => (id === p.proposal.id ? null : id))}
                    className="cursor-pointer"
                  >
                    {isAccepted && <circle cx={x} cy={y} r={9} fill="none" stroke="#16a34a" strokeWidth={2} />}
                    {isTarget ? (
                      <rect x={x - 4} y={y - 4} width={8} height={8} fill={color} opacity={p.proposal.review_status === "unreviewed" ? 0.5 : 1} />
                    ) : (
                      <circle cx={x} cy={y} r={4.5} fill={color} opacity={p.proposal.review_status === "unreviewed" ? 0.5 : 1} />
                    )}
                    {hoveredId === p.proposal.id && (
                      <text x={x} y={y - 12} textAnchor="middle" fontSize={11} fill="#171717" fontWeight={500}>
                        {formatPrice(p.price)} · {formatDate(p.date.toISOString().slice(0, 10))}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-neutral-600">
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
      </div>
      {unplottable > 0 && (
        <p className="mt-1 text-xs text-neutral-400">
          {unplottable} proposal{unplottable === 1 ? "" : "s"} not shown (no per-share price, e.g. premium-only offers) — see the timeline below.
        </p>
      )}
    </div>
  );
}
