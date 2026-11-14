import type { PctBumpBucket } from "@/lib/homeStats";

// Server-rendered, no client JS -- the hero loads one static SVG, not a
// charting bundle. Open-ended top/bottom buckets absorb the occasional
// extraction outlier from not-yet-reviewed deals without letting one
// data point dwarf the rest of the distribution.
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
            <text x={x + barWidth / 2} y={y - 6} textAnchor="middle" fontSize={11} fill="var(--color-ink)" className="tabular-nums">
              {bucket.count}
            </text>
            <rect x={x} y={y} width={barWidth} height={Math.max(barHeight, 1)} rx={2} fill="var(--color-gold)" />
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
