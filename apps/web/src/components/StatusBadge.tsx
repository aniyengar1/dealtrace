import type { ReviewStatus } from "@/lib/types";

// Unreviewed facts are marked "unverified" everywhere they appear --
// this is the one place that rule is implemented, so every surface
// (deal page, review queue) stays consistent by construction.
export function ReviewStatusBadge({ status }: { status: ReviewStatus }) {
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
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-dashed border-amber-400 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700">
      unverified
    </span>
  );
}

export function ValidationBadge({ passed }: { passed: boolean }) {
  return passed ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600">
      quotes check out
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-orange-50 px-2 py-0.5 text-xs text-orange-700">
      quote check failed
    </span>
  );
}

// Thin wrapper so any clickable fact row gets the same dashed-outline
// "unverified" treatment without each caller re-deriving the condition.
export function factRowClassName(status: ReviewStatus, extra = ""): string {
  const base = "cursor-pointer transition-colors hover:bg-neutral-50";
  const unreviewed = status === "unreviewed" ? "border-l-2 border-amber-400" : "border-l-2 border-transparent";
  return `${base} ${unreviewed} ${extra}`;
}
