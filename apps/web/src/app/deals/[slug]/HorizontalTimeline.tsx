"use client";

import { useMemo } from "react";
import type { EventRow } from "@/lib/types";
import { eventCategory, EVENT_CATEGORY_LABELS, EVENT_CATEGORY_COLORS, type EventCategory } from "@/lib/eventCategories";
import { eventTypeLabel, CORE_EVENT_TYPES } from "@/lib/labels";
import { formatEventDate } from "@/lib/format";

const LANE_HEIGHT = 40;
const MAX_AXIS_TICKS = 5;
const CATEGORY_ORDER: EventCategory[] = ["contact", "diligence", "governance", "bid", "conclusion", "other"];

function monthTicks(start: Date, end: Date): Date[] {
  const ticks: Date[] = [];
  const cursor = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth(), 1));
  while (cursor <= end) {
    ticks.push(new Date(cursor));
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }
  return ticks;
}

// Thinned to a handful of evenly-spaced ticks regardless of how many
// months the process spanned -- a percentage-based axis (see xOf
// below) has no fixed pixel width to measure against, so ticks are
// capped by count, not by a measured label-width check.
function thinTicks(ticks: Date[], max: number): Date[] {
  if (ticks.length <= max) return ticks;
  const picked: Date[] = [];
  for (let i = 0; i < max; i++) {
    const idx = Math.round((i * (ticks.length - 1)) / (max - 1));
    if (picked[picked.length - 1] !== ticks[idx]) picked.push(ticks[idx]);
  }
  return picked;
}

export function HorizontalTimeline({
  events,
  onInspect,
}: {
  events: EventRow[];
  onInspect: (e: EventRow) => void;
}) {
  const dated = useMemo(
    () =>
      events
        .filter((e) => e.date_start !== null)
        .map((e) => ({ event: e, date: new Date(`${e.date_start}T00:00:00Z`) })),
    [events]
  );
  const undatedCount = events.length - dated.length;

  // Spans first dated event -> last dated event, which in practice is
  // the signing (every included deal's latest "signing" event is its
  // chronologically last dated event, same assumption the deal
  // summary's own signing-date figure already relies on).
  const { minDate, maxDate } = useMemo(() => {
    if (dated.length === 0) return { minDate: new Date(), maxDate: new Date() };
    const times = dated.map((d) => d.date.getTime());
    return { minDate: new Date(Math.min(...times)), maxDate: new Date(Math.max(...times)) };
  }, [dated]);

  // Percentage of the container's own width, not a fixed pixel scale --
  // the chart always fits whatever space it's given (no MIN_WIDTH, no
  // horizontal scroll, no clipped edge labels on a narrow phone).
  const pctOf = (d: Date) => {
    const span = Math.max(1, maxDate.getTime() - minDate.getTime());
    return ((d.getTime() - minDate.getTime()) / span) * 100;
  };

  const byCategory = useMemo(() => {
    const map = new Map<EventCategory, { event: EventRow; date: Date }[]>();
    for (const d of dated) {
      const cat = eventCategory(d.event.event_type);
      const list = map.get(cat) ?? [];
      list.push(d);
      map.set(cat, list);
    }
    return map;
  }, [dated]);

  const presentCategories = CATEGORY_ORDER.filter((c) => (byCategory.get(c)?.length ?? 0) > 0);
  const ticks = dated.length > 0 ? thinTicks(monthTicks(minDate, maxDate), MAX_AXIS_TICKS) : [];

  if (dated.length === 0) {
    return <p className="text-sm text-ink-muted">No dated events to plot on the timeline.</p>;
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      {/* Axis: first tick left-anchored, last tick right-anchored, the
          rest centered -- an edge tick's own label width never pushes
          past the container's bounds this way. */}
      <div className="relative ml-0 h-5 sm:ml-24">
        {ticks.map((t, i) => {
          const pct = pctOf(t);
          const anchorClass = i === 0 ? "" : i === ticks.length - 1 ? "-translate-x-full" : "-translate-x-1/2";
          return (
            <span
              key={t.getTime()}
              className={`absolute top-0 whitespace-nowrap font-mono text-[10px] text-ink-faint ${anchorClass}`}
              style={{ left: `${pct}%` }}
            >
              {t.toLocaleDateString("en-US", { month: "short", year: "2-digit", timeZone: "UTC" })}
            </span>
          );
        })}
      </div>

      <div className="mt-1 space-y-1">
        {presentCategories.map((cat) => (
          <div key={cat} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-3">
            <span className="flex shrink-0 items-center gap-1.5 text-xs text-ink-muted sm:w-24">
              <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: EVENT_CATEGORY_COLORS[cat] }} />
              {EVENT_CATEGORY_LABELS[cat]}
            </span>
            <div className="relative flex-1 border-t border-border" style={{ height: LANE_HEIGHT }}>
              {byCategory.get(cat)!.map(({ event, date }) => {
                const isCore = CORE_EVENT_TYPES.has(event.event_type);
                const size = isCore ? 13 : 9;
                const pct = pctOf(date);
                const opacity = event.review_status === "unreviewed" ? 0.6 : 1;
                return (
                  <button
                    key={event.id}
                    onClick={() => onInspect(event)}
                    title={`${formatEventDate(event)} — ${eventTypeLabel(event.event_type)}: ${event.summary}`}
                    className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface transition-transform hover:scale-125 focus-visible:scale-125"
                    style={{ left: `${pct}%`, width: size, height: size, backgroundColor: EVENT_CATEGORY_COLORS[cat], opacity }}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {undatedCount > 0 && (
        <p className="mt-2 text-xs text-ink-faint">
          {undatedCount} event{undatedCount === 1 ? "" : "s"} without a resolvable date not shown above — see the full list below.
        </p>
      )}
    </div>
  );
}
