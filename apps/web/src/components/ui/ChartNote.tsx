// OWID/Our-World-in-Data-style chart furniture: one plain-English
// sentence explaining what's plotted, directly under the title (never
// buried in a tooltip), plus a one-line source credit. Shared so every
// chart on the site states its own definition the same way instead of
// each page inventing its own phrasing/markup.
export function ChartNote({ definition, source }: { definition: string; source: string }) {
  return (
    <div className="mt-1 space-y-0.5">
      <p className="text-xs text-ink-muted">{definition}</p>
      <p className="text-xs text-ink-faint">Source: {source}</p>
    </div>
  );
}
