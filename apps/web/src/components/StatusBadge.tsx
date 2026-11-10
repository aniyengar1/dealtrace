import type { ReviewStatus } from "@/lib/types";

// "deal" context (the deal page) relies on one deal-level "X of Y
// reviewed" banner instead of a chip on every fact, so an unreviewed
// fact renders no badge at all there -- only a human decision
// (confirmed/rejected) is worth a per-fact chip. "review" context (the
// review queue) is a focused one-fact-at-a-time view where seeing the
// current state matters, so unreviewed still renders, just relabeled.
export function ReviewStatusBadge({
  status,
  context = "deal",
}: {
  status: ReviewStatus;
  context?: "deal" | "review";
}) {
  if (status === "confirmed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
        verified
      </span>
    );
  }
  if (status === "rejected") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700">
        rejected
      </span>
    );
  }
  if (context === "deal") return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-dashed border-amber-400 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
      not yet reviewed
    </span>
  );
}

export function ValidationBadge({ passed }: { passed: boolean }) {
  return passed ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600">
      source check passed
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2 py-0.5 text-xs text-orange-700">
      source check failed
    </span>
  );
}

export function factRowClassName(extra = ""): string {
  return `cursor-pointer transition-colors hover:bg-neutral-50 ${extra}`;
}

export function ReviewProgressBanner({ reviewed, total }: { reviewed: number; total: number }) {
  const pct = total > 0 ? Math.round((reviewed / total) * 100) : 0;
  return (
    <div className="flex items-center gap-3 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm">
      <div className="h-1.5 w-32 overflow-hidden rounded-full bg-neutral-200">
        <div className="h-full rounded-full bg-emerald-500" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-neutral-600">
        <span className="font-medium text-neutral-900">{reviewed}</span> of {total} facts reviewed
      </span>
    </div>
  );
}
