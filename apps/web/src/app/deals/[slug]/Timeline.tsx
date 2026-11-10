"use client";

import { useMemo, useState } from "react";
import type { EventRow } from "@/lib/types";
import { formatEventDate } from "@/lib/format";
import { eventTypeLabel, CORE_EVENT_TYPES } from "@/lib/labels";
import { ReviewStatusBadge, factRowClassName } from "@/components/StatusBadge";

function chipClassName(active: boolean, isCore: boolean): string {
  if (active && isCore) return "bg-neutral-900 text-white border border-neutral-900";
  if (active) return "bg-neutral-200 text-neutral-700 border border-neutral-200";
  if (isCore) return "bg-white text-neutral-700 border-2 border-neutral-900";
  return "bg-white text-neutral-400 border border-neutral-200";
}

export function Timeline({
  events,
  onInspect,
}: {
  events: EventRow[];
  onInspect: (e: EventRow) => void;
}) {
  const allTypes = useMemo(
    () => Array.from(new Set(events.map((e) => e.event_type))).sort(),
    [events]
  );
  const [activeTypes, setActiveTypes] = useState<Set<string>>(new Set(allTypes));

  function toggleType(type: string) {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  const visible = events.filter((e) => activeTypes.has(e.event_type));

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {allTypes.map((type) => {
          const active = activeTypes.has(type);
          const isCore = CORE_EVENT_TYPES.has(type);
          return (
            <button
              key={type}
              onClick={() => toggleType(type)}
              className={`rounded-full px-2.5 py-1 text-xs transition-colors ${chipClassName(active, isCore)}`}
            >
              {eventTypeLabel(type)}
            </button>
          );
        })}
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
              <span className="w-32 flex-shrink-0 tabular-nums text-xs text-neutral-500">
                {formatEventDate(event)}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs ${
                      isCore ? "bg-neutral-900 text-white" : "bg-neutral-100 text-neutral-600"
                    }`}
                  >
                    {eventTypeLabel(event.event_type)}
                  </span>
                  <ReviewStatusBadge status={event.review_status} />
                </div>
                <p className={`mt-0.5 text-sm ${isCore ? "font-medium text-neutral-900" : "text-neutral-600"}`}>
                  {event.summary}
                </p>
              </div>
            </li>
          );
        })}
        {visible.length === 0 && (
          <li className="px-2 py-6 text-center text-sm text-neutral-400">No events match the selected filters.</li>
        )}
      </ol>
    </div>
  );
}
