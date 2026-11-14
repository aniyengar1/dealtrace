"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { EventRow } from "@/lib/types";
import { formatEventDate } from "@/lib/format";
import { eventTypeLabel, CORE_EVENT_TYPES } from "@/lib/labels";
import { ReviewStatusBadge, factRowClassName } from "@/components/StatusBadge";

function chipClassName(active: boolean, isCore: boolean): string {
  if (active && isCore) return "bg-gold text-gold-ink border border-gold";
  if (active) return "bg-surface-raised text-ink border border-border-strong";
  if (isCore) return "bg-transparent text-ink-muted border-2 border-border-strong";
  return "bg-transparent text-ink-faint border border-border";
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
        {visible.map((event, i) => {
          const isCore = CORE_EVENT_TYPES.has(event.event_type);
          return (
            <motion.li
              key={event.id}
              onClick={() => onInspect(event)}
              className={factRowClassName("flex gap-3 rounded px-2 py-2")}
              initial={{ opacity: 0, x: -8 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.8 }}
              transition={{ duration: 0.25, delay: Math.min(i * 0.03, 0.3) }}
            >
              <span className="w-32 flex-shrink-0 tabular-nums text-xs text-ink-muted">
                {formatEventDate(event)}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded px-1.5 py-0.5 text-xs ${
                      isCore ? "bg-gold text-gold-ink" : "bg-surface-raised text-ink-muted"
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
            </motion.li>
          );
        })}
        {visible.length === 0 && (
          <li className="px-2 py-6 text-center text-sm text-ink-faint">No events match the selected filters.</li>
        )}
      </ol>
    </div>
  );
}
