"use client";

import { motion } from "framer-motion";
import type { PctBumpBucket } from "@/lib/homeStats";

// Client component (bars grow in on mount) -- the hero loads one small
// SVG + a few motion props, not a charting bundle. Open-ended top/bottom
// buckets absorb the occasional extraction outlier from not-yet-reviewed
// deals without letting one data point dwarf the rest of the distribution.
export function HeroBumpChart({ data }: { data: PctBumpBucket[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  const width = 340;
  const barGap = 10;
  const barWidth = (width - barGap * (data.length - 1)) / data.length;
  const plotHeight = 140;
  const labelHeight = 28;
  const height = plotHeight + labelHeight;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-auto w-full"
      role="img"
      aria-label="Distribution of percent change from first proposal to final signed price, across all deals"
    >
      {data.map((bucket, i) => {
        const barHeight = (bucket.count / max) * (plotHeight - 24);
        const x = i * (barWidth + barGap);
        const y = plotHeight - barHeight;
        return (
          <g key={bucket.label}>
            <motion.text
              x={x + barWidth / 2}
              y={y - 6}
              textAnchor="middle"
              fontSize={11}
              fill="var(--color-ink)"
              className="tabular-nums"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 + i * 0.07, duration: 0.3 }}
            >
              {bucket.count}
            </motion.text>
            <motion.rect
              x={x}
              width={barWidth}
              rx={2}
              fill="var(--color-gold)"
              initial={{ y: plotHeight, height: 0 }}
              animate={{ y, height: Math.max(barHeight, 1) }}
              transition={{ delay: i * 0.07, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
            />
            <text
              x={x + barWidth / 2}
              y={plotHeight + 18}
              textAnchor="middle"
              fontSize={10}
              fill="var(--color-ink-muted)"
            >
              {bucket.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
