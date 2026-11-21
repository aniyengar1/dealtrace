"use client";

import { useEffect } from "react";
import type { Fact, ParagraphRow } from "@/lib/types";
import { renderHighlighted } from "@/lib/highlight";
import { ReviewStatusBadge, ValidationBadge } from "@/components/StatusBadge";
import { formatEventDate, formatPriceRange, formatMultipleRange } from "@/lib/format";
import { eventTypeLabel, proposalKindLabel, proposalStatusLabel, valuationMethodLabel } from "@/lib/labels";

function factTitle(fact: Fact): string {
  if (fact.record_type === "Event") return eventTypeLabel(fact.event_type);
  if (fact.record_type === "Proposal") return proposalKindLabel(fact.proposal_kind);
  return `${fact.advisor} — ${valuationMethodLabel(fact.method)}`;
}

function FactFields({ fact }: { fact: Fact }) {
  if (fact.record_type === "Event") {
    return (
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-ink-muted">Date</dt>
        <dd>{formatEventDate(fact)}</dd>
        <dt className="text-ink-muted">Parties</dt>
        <dd>{fact.parties.join(", ") || "—"}</dd>
        <dt className="text-ink-muted">Summary</dt>
        <dd>{fact.summary}</dd>
      </dl>
    );
  }
  if (fact.record_type === "Proposal") {
    return (
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-ink-muted">Date</dt>
        <dd>{fact.date_text}</dd>
        <dt className="text-ink-muted">From / to</dt>
        <dd>
          {fact.proposer} → {fact.recipient}
        </dd>
        <dt className="text-ink-muted">Price</dt>
        <dd className="tabular-nums">{formatPriceRange(fact.price_low, fact.price_high)}</dd>
        {fact.premium_pct !== null && (
          <>
            <dt className="text-ink-muted">Premium</dt>
            <dd className="tabular-nums">{fact.premium_pct.toFixed(1)}%</dd>
          </>
        )}
        <dt className="text-ink-muted">Status</dt>
        <dd>{proposalStatusLabel(fact.status)}</dd>
      </dl>
    );
  }
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
      <dt className="text-ink-muted">Metric</dt>
      <dd>{fact.metric}</dd>
      <dt className="text-ink-muted">Multiple</dt>
      <dd className="tabular-nums">{formatMultipleRange(fact.multiple_low, fact.multiple_high)}</dd>
      <dt className="text-ink-muted">Implied price</dt>
      <dd className="tabular-nums">
        {formatPriceRange(fact.implied_price_low, fact.implied_price_high)}
      </dd>
      {fact.key_assumptions.length > 0 && (
        <>
          <dt className="text-ink-muted">Assumptions</dt>
          <dd>{fact.key_assumptions.join("; ")}</dd>
        </>
      )}
    </dl>
  );
}

export function EvidenceDrawer({
  fact,
  paragraphs,
  onClose,
}: {
  fact: Fact | null;
  paragraphs: Record<string, ParagraphRow>;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!fact) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fact, onClose]);

  if (!fact) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative flex h-full w-full max-w-lg flex-col overflow-y-auto border-l border-border bg-surface shadow-xl">
        <div className="flex items-start justify-between border-b border-border px-5 py-4">
          <div>
            <div className="text-xs uppercase tracking-wide text-ink-muted">
              {fact.record_type}
            </div>
            <h2 className="text-base font-semibold">{factTitle(fact)}</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded px-2 py-1 text-sm text-ink-muted hover:bg-surface-raised"
            aria-label="Close"
          >
            Esc ✕
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2 border-b border-border px-5 py-3">
          <ReviewStatusBadge status={fact.review_status} />
          <ValidationBadge passed={fact.passed} />
        </div>

        <div className="border-b border-border px-5 py-4">
          <FactFields fact={fact} />
          {fact.failure_reasons.length > 0 && (
            <div className="mt-3 rounded bg-negative/15 px-3 py-2 text-xs text-negative">
              {fact.failure_reasons.join("; ")}
            </div>
          )}
          {fact.reviewer_note && (
            <div className="mt-3 rounded bg-surface-raised px-3 py-2 text-xs text-ink">
              <span className="font-medium">Reviewer note: </span>
              {fact.reviewer_note}
            </div>
          )}
        </div>

        <div className="flex-1 px-5 py-4">
          <h3 className="text-xs font-medium uppercase tracking-wide text-ink-muted">
            Source paragraph{fact.source_paragraph_ids.length > 1 ? "s" : ""}
          </h3>
          <div className="mt-2 space-y-4">
            {fact.source_paragraph_ids.map((pid) => {
              const paragraph = paragraphs[pid];
              return (
                <div key={pid} className="rounded border border-border p-3">
                  <div className="mb-1.5 flex items-center justify-between text-xs text-ink-muted">
                    <span className="font-mono">{pid}</span>
                    {paragraph && <span>{paragraph.section_key.replace(/_/g, " ")}</span>}
                  </div>
                  <p className="text-sm leading-relaxed">
                    {paragraph
                      ? renderHighlighted(paragraph.text, fact.source_quotes)
                      : "(paragraph not found)"}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
