// Minimal 1px-stroke line diagrams, one per pipeline step -- black/
// silver, no fill, no color beyond the page's own ink/accent tokens.
// Deliberately plain geometric shapes (a lens, a funnel, a document
// with a cut line, a check-in-a-circle, a stack) rather than a
// licensed icon set, so they read as diagrams rather than illustration.
export type StepKind = "discover" | "classify" | "extract" | "validate" | "load";

const PATHS: Record<StepKind, React.ReactNode> = {
  discover: (
    <>
      <circle cx="13" cy="13" r="8" />
      <line x1="19" y1="19" x2="27" y2="27" />
    </>
  ),
  classify: (
    <>
      <path d="M4 6h24l-9 11v9l-6 3v-12z" />
    </>
  ),
  extract: (
    <>
      <rect x="7" y="4" width="18" height="24" rx="1" />
      <line x1="11" y1="11" x2="21" y2="11" strokeDasharray="2 2" />
      <line x1="11" y1="16" x2="21" y2="16" />
      <line x1="11" y1="21" x2="17" y2="21" />
    </>
  ),
  validate: (
    <>
      <circle cx="16" cy="16" r="12" />
      <path d="M10 16l4 4 8-8" />
    </>
  ),
  load: (
    <>
      <ellipse cx="16" cy="8" rx="10" ry="4" />
      <path d="M6 8v16c0 2.2 4.5 4 10 4s10-1.8 10-4V8" />
      <path d="M6 16c0 2.2 4.5 4 10 4s10-1.8 10-4" />
    </>
  ),
};

export function StepDiagram({ kind, step }: { kind: StepKind; step: number }) {
  return (
    <div className="flex items-center gap-3">
      <svg
        width="32"
        height="32"
        viewBox="0 0 32 32"
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth="1"
        aria-hidden
        className="shrink-0"
      >
        {PATHS[kind]}
      </svg>
      <span className="font-mono text-xs tracking-wide text-ink-faint">STEP {String(step).padStart(2, "0")}</span>
    </div>
  );
}
