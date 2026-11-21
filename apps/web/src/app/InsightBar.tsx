// One reusable horizontal-bar shape for every "what the data says"
// insight instead of three bespoke chart types -- a single visual
// language (filled bar against a labeled domain, optional reference
// line) reads faster across three adjacent cards than three different
// chart idioms would.
export function InsightBar({
  value,
  domain,
  valueLabel,
  domainLabels,
  referenceAt,
}: {
  value: number;
  domain: [number, number];
  valueLabel: string;
  domainLabels: [string, string];
  referenceAt?: number;
}) {
  const [min, max] = domain;
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  const refPct = referenceAt !== undefined ? Math.max(0, Math.min(100, ((referenceAt - min) / (max - min)) * 100)) : null;

  return (
    <div>
      <p className="font-serif text-3xl text-accent tabular-nums">{valueLabel}</p>
      <div className="relative mt-3 h-2.5 rounded-full bg-surface-raised">
        <div className="absolute inset-y-0 left-0 rounded-full bg-accent" style={{ width: `${pct}%` }} />
        {refPct !== null && (
          <div className="absolute top-1/2 h-3.5 w-0.5 -translate-y-1/2 bg-ink-faint" style={{ left: `${refPct}%` }} />
        )}
      </div>
      <div className="mt-1 flex justify-between text-xs text-ink-faint">
        <span>{domainLabels[0]}</span>
        <span>{domainLabels[1]}</span>
      </div>
    </div>
  );
}
