"use client";

import { useMemo, useState } from "react";
import type { EventRow } from "@/lib/types";
import { formatEventDate } from "@/lib/format";
import { eventTypeLabel, CORE_EVENT_TYPES } from "@/lib/labels";
import {
  eventCategory,
  EVENT_CATEGORY_LABELS,
  EVENT_CATEGORY_COLORS,
  type EventCategory,
} from "@/lib/eventCategories";
import { ReviewStatusBadge, factRowClassName } from "@/components/StatusBadge";

const CATEGORY_ORDER: EventCategory[] = ["contact", "diligence", "governance", "bid", "conclusion", "other"];

// One obvious selected style (a solid filled pill), one obvious
// unselected style (a plain outline) -- a translucent tint of the
// lane's own muted color used to carry this distinction, but with
// lane colors confined to a narrow muted band (see globals.css), a
// 22%-opacity tint of any of them reads as "about the same dark gray"
// next to an unselected chip's own dark background. Lane identity
// still shows up via the small colored dot, not the chip's fill.
function chipStyle(active: boolean): string {
  return active
    ? "border border-border-strong bg-surface-raised text-ink"
    : "border border-border bg-transparent text-ink-faint";
}

export function Timeline({
  events,
  onInspect,
}: {
  events: EventRow[];
  onInspect: (e: EventRow) => void;
}) {
  const counts = useMemo(() => {
    const m = new Map<EventCategory, number>();
    for (const e of events) {
      const cat = eventCategory(e.event_type);
      m.set(cat, (m.get(cat) ?? 0) + 1);
    }
    return m;
  }, [events]);
  const presentCategories = CATEGORY_ORDER.filter((c) => (counts.get(c) ?? 0) > 0);
  const [activeCategories, setActiveCategories] = useState<Set<EventCategory>>(new Set(presentCategories));

  function toggleCategory(cat: EventCategory) {
    setActiveCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  }

  const visible = events.filter((e) => activeCategories.has(eventCategory(e.event_type)));
  const allCleared = activeCategories.size === 0;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        {presentCategories.map((cat) => {
          const active = activeCategories.has(cat);
          return (
            <button
              key={cat}
              onClick={() => toggleCategory(cat)}
              aria-pressed={active}
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${chipStyle(active)}`}
            >
              <span
                className="inline-block h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: EVENT_CATEGORY_COLORS[cat], opacity: active ? 1 : 0.5 }}
              />
              {EVENT_CATEGORY_LABELS[cat]} <span className="tabular-nums opacity-70">({counts.get(cat)})</span>
            </button>
          );
        })}
        <button
          onClick={() => setActiveCategories(allCleared ? new Set(presentCategories) : new Set())}
          className="ml-1 rounded-full px-2.5 py-1 text-xs font-medium text-ink-muted underline-offset-2 hover:text-ink hover:underline"
        >
          {allCleared ? "Select all" : "Clear"}
        </button>
      </div>

      <ol className="space-y-1">
        {visible.map((event) => {
          const isCore = CORE_EVENT_TYPES.has(event.event_type);
          return (
            <li
              key={event.id}
              onClick={() => onInspect(event)}
              className={factRowClassName("flex gap-3 rounded px-2 py-2")}
            >
              <span className="w-32 flex-shrink-0 tabular-nums text-xs text-ink-muted">
                {formatEventDate(event)}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs ${
                      isCore ? "bg-accent text-accent-ink" : "bg-surface-raised text-ink-muted"
                    }`}
                  >
                    {eventTypeLabel(event.event_type)}
                  </span>
                  <ReviewStatusBadge status={event.review_status} />
                </div>
                <p className={`mt-0.5 text-sm ${isCore ? "font-medium text-ink" : "text-ink-muted"}`}>
                  {event.summary}
                </p>
              </div>
            </li>
          );
        })}
        {visible.length === 0 && (
          <li className="px-2 py-6 text-center text-sm text-ink-faint">No events match the selected filters.</li>
        )}
      </ol>
    </div>
  );
}
