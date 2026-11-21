"use client";

import { useMemo } from "react";
import type { EventRow } from "@/lib/types";
import { eventCategory, EVENT_CATEGORY_LABELS, EVENT_CATEGORY_COLORS, type EventCategory } from "@/lib/eventCategories";
import { eventTypeLabel, CORE_EVENT_TYPES } from "@/lib/labels";
import { formatEventDate } from "@/lib/format";

const PX_PER_DAY = 3;
const MIN_WIDTH = 640;
const LANE_HEIGHT = 40;
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

  const { minDate, maxDate, width } = useMemo(() => {
    if (dated.length === 0) return { minDate: new Date(), maxDate: new Date(), width: MIN_WIDTH };
    const times = dated.map((d) => d.date.getTime());
    const min = new Date(Math.min(...times));
    const max = new Date(Math.max(...times));
    const days = Math.max(1, (max.getTime() - min.getTime()) / (1000 * 60 * 60 * 24));
    return { minDate: min, maxDate: max, width: Math.max(MIN_WIDTH, days * PX_PER_DAY + 80) };
  }, [dated]);

  const xOf = (d: Date) => {
    const span = Math.max(1, maxDate.getTime() - minDate.getTime());
    return 40 + ((d.getTime() - minDate.getTime()) / span) * (width - 80);
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
  const ticks = dated.length > 0 ? monthTicks(minDate, maxDate) : [];

  if (dated.length === 0) {
    return <p className="text-sm text-ink-muted">No dated events to plot on the timeline.</p>;
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-muted">
        {presentCategories.map((cat) => (
          <span key={cat} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: EVENT_CATEGORY_COLORS[cat] }} />
            {EVENT_CATEGORY_LABELS[cat]}
          </span>
        ))}
      </div>

      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        <div style={{ width }} className="relative pb-2 pt-6">
          {ticks.map((t) => (
            <div key={t.getTime()} className="absolute top-0 flex flex-col items-start" style={{ left: xOf(t) }}>
              <div className="h-2 w-px bg-border-strong" />
              <span className="mt-0.5 whitespace-nowrap font-mono text-[10px] text-ink-faint">
                {t.toLocaleDateString("en-US", { month: "short", year: "2-digit", timeZone: "UTC" })}
              </span>
            </div>
          ))}

          {presentCategories.map((cat) => (
            <div key={cat} className="relative border-t border-border" style={{ height: LANE_HEIGHT }}>
              {byCategory.get(cat)!.map(({ event, date }) => {
                const isCore = CORE_EVENT_TYPES.has(event.event_type);
                const size = isCore ? 13 : 9;
                const left = xOf(date);
                const opacity = event.review_status === "unreviewed" ? 0.6 : 1;
                return (
                  <button
                    key={event.id}
                    onClick={() => onInspect(event)}
                    title={`${formatEventDate(event)} — ${eventTypeLabel(event.event_type)}: ${event.summary}`}
                    className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-surface transition-transform hover:scale-125 focus-visible:scale-125"
                    style={{ left, width: size, height: size, backgroundColor: EVENT_CATEGORY_COLORS[cat], opacity }}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </div>
      {undatedCount > 0 && (
        <p className="mt-2 text-xs text-ink-faint">
          {undatedCount} event{undatedCount === 1 ? "" : "s"} without a resolvable date not shown above — see the full list below.
        </p>
      )}
    </div>
  );
}
