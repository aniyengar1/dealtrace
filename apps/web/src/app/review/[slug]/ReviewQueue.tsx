"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import type { Fact, FactType, ParagraphRow } from "@/lib/types";
import { renderHighlighted } from "@/lib/highlight";
import { ReviewStatusBadge, ValidationBadge } from "@/components/StatusBadge";
import { eventTypeLabel, proposalKindLabel, valuationMethodLabel, CORE_EVENT_TYPES } from "@/lib/labels";
import { approveFactAction, correctFactAction, rejectFactAction } from "./actions";

// Proposals first (the facts that most directly drive the deal
// narrative), then core-type events, then everything else (non-core
// events and valuations) -- a stable sort, so ties keep their original
// date-ish order from getAllFactsForRun.
function factTier(fact: Fact): number {
  if (fact.record_type === "Proposal") return 0;
  if (fact.record_type === "Event") return CORE_EVENT_TYPES.has(fact.event_type) ? 1 : 2;
  return 3;
}

function isCoreOrProposal(fact: Fact): boolean {
  if (fact.record_type === "Proposal") return true;
  if (fact.record_type === "Event") return CORE_EVENT_TYPES.has(fact.event_type);
  return false;
}

type FieldType = "text" | "number" | "textarea" | "array" | "select";
interface FieldConfig {
  key: string;
  label: string;
  type: FieldType;
  options?: string[];
}

const FIELD_CONFIG: Record<FactType, FieldConfig[]> = {
  Event: [
    { key: "event_type", label: "Event type", type: "text" },
    { key: "date_text", label: "Date (as written)", type: "text" },
    { key: "date_start", label: "Date start (ISO)", type: "text" },
    { key: "date_end", label: "Date end (ISO)", type: "text" },
    { key: "date_precision", label: "Date precision", type: "select", options: ["day", "month", "range", "unknown"] },
    { key: "parties", label: "Parties", type: "array" },
    { key: "summary", label: "Summary", type: "textarea" },
  ],
  Proposal: [
    { key: "date_text", label: "Date (as written)", type: "text" },
    { key: "date_resolved", label: "Date resolved (ISO)", type: "text" },
    { key: "proposer", label: "Proposer", type: "text" },
    { key: "recipient", label: "Recipient", type: "text" },
    { key: "price_low", label: "Price low", type: "number" },
    { key: "price_high", label: "Price high", type: "number" },
    { key: "premium_pct", label: "Premium %", type: "number" },
    { key: "currency", label: "Currency", type: "text" },
    { key: "consideration_type", label: "Consideration type", type: "select", options: ["cash", "stock", "mixed", "unknown"] },
    {
      key: "proposal_kind",
      label: "Proposal kind",
      type: "select",
      options: ["non_binding_indication", "formal_bid", "counteroffer", "revised_bid", "suggested_valuation"],
    },
    { key: "status", label: "Status", type: "select", options: ["open", "rejected", "superseded", "accepted", "withdrawn"] },
  ],
  ValuationAnalysis: [
    { key: "advisor", label: "Advisor", type: "text" },
    { key: "method", label: "Method", type: "select", options: ["trading_comps", "precedent_transactions", "dcf", "other"] },
    { key: "metric", label: "Metric", type: "text" },
    { key: "multiple_low", label: "Multiple low", type: "number" },
    { key: "multiple_high", label: "Multiple high", type: "number" },
    { key: "implied_price_low", label: "Implied price low", type: "number" },
    { key: "implied_price_high", label: "Implied price high", type: "number" },
    { key: "key_assumptions", label: "Key assumptions", type: "array" },
  ],
};

function fieldValue(fact: Fact, key: string): unknown {
  return (fact as unknown as Record<string, unknown>)[key];
}

function toEditString(value: unknown, type: FieldType): string {
  if (value === null || value === undefined) return "";
  if (type === "array" && Array.isArray(value)) return value.join("; ");
  return String(value);
}

function fromEditString(value: string, type: FieldType): unknown {
  if (type === "array") {
    return value
      .split(";")
      .map((s) => s.trim())
      .filter(Boolean);
  }
  if (type === "number") {
    return value.trim() === "" ? null : Number(value);
  }
  return value.trim() === "" ? null : value;
}

function factSummaryLine(fact: Fact): string {
  if (fact.record_type === "Event") return eventTypeLabel(fact.event_type);
  if (fact.record_type === "Proposal") return `${fact.proposer} → ${fact.recipient} (${proposalKindLabel(fact.proposal_kind)})`;
  return `${fact.advisor} — ${valuationMethodLabel(fact.method)}`;
}

export function ReviewQueue({
  slug,
  initialFacts,
  paragraphs,
}: {
  slug: string;
  initialFacts: Fact[];
  paragraphs: Record<string, ParagraphRow>;
}) {
  const [facts, setFacts] = useState(() => [...initialFacts].sort((a, b) => factTier(a) - factTier(b)));
  const [coreOnly, setCoreOnly] = useState(false);
  const visibleFacts = useMemo(
    () => (coreOnly ? facts.filter(isCoreOrProposal) : facts),
    [facts, coreOnly]
  );
  const [index, setIndex] = useState(() => {
    const firstUnreviewed = visibleFacts.findIndex((f) => f.review_status === "unreviewed");
    return firstUnreviewed === -1 ? 0 : firstUnreviewed;
  });
  const [mode, setMode] = useState<"view" | "correct" | "reject">("view");
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [noteValue, setNoteValue] = useState("");
  const [pending, setPending] = useState(false);
  const noteInputRef = useRef<HTMLTextAreaElement>(null);

  const current = visibleFacts[index];
  const fields = current ? FIELD_CONFIG[current.record_type] : [];
  const reviewedCount = facts.filter((f) => f.review_status !== "unreviewed").length;

  function resetModeState() {
    setMode("view");
    setEditValues({});
    setNoteValue("");
  }

  function goTo(newIndex: number) {
    if (newIndex < 0 || newIndex >= visibleFacts.length) return;
    setIndex(newIndex);
    resetModeState();
  }

  function toggleCoreOnly() {
    setCoreOnly((v) => !v);
    setIndex(0);
    resetModeState();
  }

  function updateCurrentFact(patch: Record<string, unknown>) {
    if (!current) return;
    setFacts((prev) => prev.map((f) => (f.id === current.id ? ({ ...f, ...patch } as Fact) : f)));
  }

  async function handleApprove() {
    if (!current || pending) return;
    setPending(true);
    await approveFactAction(slug, current.record_type, current.id);
    updateCurrentFact({ review_status: "confirmed" });
    setPending(false);
    goTo(index + 1);
  }

  function startReject() {
    setMode("reject");
    setTimeout(() => noteInputRef.current?.focus(), 0);
  }

  async function submitReject() {
    if (!current || pending || noteValue.trim() === "") return;
    setPending(true);
    await rejectFactAction(slug, current.record_type, current.id, noteValue.trim());
    updateCurrentFact({ review_status: "rejected", reviewer_note: noteValue.trim() });
    setPending(false);
    goTo(index + 1);
  }

  function startCorrect() {
    if (!current) return;
    const initial: Record<string, string> = {};
    for (const field of FIELD_CONFIG[current.record_type]) {
      initial[field.key] = toEditString(fieldValue(current, field.key), field.type);
    }
    setEditValues(initial);
    setNoteValue(current.reviewer_note ?? "");
    setMode("correct");
  }

  async function submitCorrect() {
    if (!current || pending) return;
    setPending(true);
    const parsed: Record<string, unknown> = {};
    for (const field of fields) {
      parsed[field.key] = fromEditString(editValues[field.key] ?? "", field.type);
    }
    await correctFactAction(slug, current.record_type, current.id, parsed, noteValue.trim() || null);
    updateCurrentFact({ ...parsed, review_status: "confirmed", reviewer_note: noteValue.trim() || null });
    setPending(false);
    goTo(index + 1);
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      const isTyping = ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
      if (isTyping) {
        if (e.key === "Escape") resetModeState();
        return;
      }
      if (mode !== "view") {
        if (e.key === "Escape") resetModeState();
        return;
      }
      if (e.key === "a") handleApprove();
      else if (e.key === "c") startCorrect();
      else if (e.key === "r") startReject();
      else if (e.key === "j") goTo(index + 1);
      else if (e.key === "k") goTo(index - 1);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, index, facts, coreOnly, pending]);

  const quotes = useMemo(() => current?.source_quotes ?? [], [current]);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between text-sm text-ink-muted">
        <div className="flex items-center gap-4">
          <span>
            {current ? `${index + 1} of ${visibleFacts.length}` : "0 of 0"}
            {coreOnly ? " (core only)" : ""} · {reviewedCount} of {facts.length} reviewed overall
          </span>
          <button
            onClick={toggleCoreOnly}
            className={`rounded-full px-2.5 py-1 text-xs transition-colors ${
              coreOnly ? "bg-gold text-gold-ink" : "border border-border-strong text-ink-muted hover:bg-surface-raised"
            }`}
          >
            Core only
          </button>
        </div>
        <span className="text-xs">
          <kbd className="rounded border border-border-strong bg-surface-raised px-1">a</kbd> approve ·{" "}
          <kbd className="rounded border border-border-strong bg-surface-raised px-1">c</kbd> correct ·{" "}
          <kbd className="rounded border border-border-strong bg-surface-raised px-1">r</kbd> reject ·{" "}
          <kbd className="rounded border border-border-strong bg-surface-raised px-1">j</kbd>/
          <kbd className="rounded border border-border-strong bg-surface-raised px-1">k</kbd> next/prev
        </span>
      </div>

      {!current ? (
        <p className="text-sm text-ink-muted">
          {facts.length === 0
            ? "No facts to review for this deal."
            : "No core facts (proposals/core events) to review -- turn off Core only to see the rest."}
        </p>
      ) : (
      <div className="grid grid-cols-2 gap-6">
        <div className="rounded-lg border border-border bg-surface p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-wide text-ink-muted">{current.record_type}</div>
              <div className="text-sm font-medium">{factSummaryLine(current)}</div>
            </div>
            <div className="flex items-center gap-2">
              <ReviewStatusBadge status={current.review_status} context="review" />
              <ValidationBadge passed={current.passed} />
            </div>
          </div>

          {mode === "correct" ? (
            <div className="space-y-2.5">
              {fields.map((field) => (
                <div key={field.key}>
                  <label className="block text-xs text-ink-muted">{field.label}</label>
                  {field.type === "textarea" ? (
                    <textarea
                      className="mt-0.5 w-full rounded border border-border-strong px-2 py-1 text-sm"
                      rows={3}
                      value={editValues[field.key] ?? ""}
                      onChange={(e) => setEditValues((v) => ({ ...v, [field.key]: e.target.value }))}
                    />
                  ) : field.type === "select" ? (
                    <select
                      className="mt-0.5 w-full rounded border border-border-strong px-2 py-1 text-sm"
                      value={editValues[field.key] ?? ""}
                      onChange={(e) => setEditValues((v) => ({ ...v, [field.key]: e.target.value }))}
                    >
                      {field.options?.map((opt) => (
                        <option key={opt} value={opt}>
                          {opt}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={field.type === "number" ? "number" : "text"}
                      step="any"
                      className="mt-0.5 w-full rounded border border-border-strong px-2 py-1 text-sm"
                      value={editValues[field.key] ?? ""}
                      onChange={(e) => setEditValues((v) => ({ ...v, [field.key]: e.target.value }))}
                    />
                  )}
                </div>
              ))}
              <div>
                <label className="block text-xs text-ink-muted">Note (optional)</label>
                <textarea
                  className="mt-0.5 w-full rounded border border-border-strong px-2 py-1 text-sm"
                  rows={2}
                  value={noteValue}
                  onChange={(e) => setNoteValue(e.target.value)}
                />
              </div>
              <div className="flex gap-2 pt-1">
                <button
                  onClick={submitCorrect}
                  disabled={pending}
                  className="rounded bg-gold px-3 py-1.5 text-sm font-medium text-gold-ink hover:bg-gold/90 disabled:opacity-50"
                >
                  Save correction
                </button>
                <button
                  onClick={resetModeState}
                  className="rounded border border-border-strong px-3 py-1.5 text-sm hover:bg-surface-raised"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                {fields.map((field) => {
                  const raw = fieldValue(current, field.key);
                  const display = toEditString(raw, field.type);
                  return (
                    <Fragment key={field.key}>
                      <dt className="text-ink-muted">{field.label}</dt>
                      <dd className="tabular-nums">{display || "—"}</dd>
                    </Fragment>
                  );
                })}
              </dl>

              {current.failure_reasons.length > 0 && (
                <div className="mt-3 rounded bg-negative/15 px-3 py-2 text-xs text-negative">
                  {current.failure_reasons.join("; ")}
                </div>
              )}
              {current.reviewer_note && (
                <div className="mt-3 rounded bg-surface-raised px-3 py-2 text-xs text-ink">
                  <span className="font-medium">Note: </span>
                  {current.reviewer_note}
                </div>
              )}

              {mode === "reject" ? (
                <div className="mt-4">
                  <label className="block text-xs text-ink-muted">Reason for rejection (required)</label>
                  <textarea
                    ref={noteInputRef}
                    className="mt-0.5 w-full rounded border border-border-strong px-2 py-1 text-sm"
                    rows={2}
                    value={noteValue}
                    onChange={(e) => setNoteValue(e.target.value)}
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={submitReject}
                      disabled={pending || noteValue.trim() === ""}
                      className="rounded bg-negative px-3 py-1.5 text-sm font-medium text-bg hover:bg-negative/90 disabled:opacity-50"
                    >
                      Confirm reject
                    </button>
                    <button
                      onClick={resetModeState}
                      className="rounded border border-border-strong px-3 py-1.5 text-sm hover:bg-surface-raised"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="mt-4 flex gap-2">
                  <button
                    onClick={handleApprove}
                    disabled={pending}
                    className="rounded bg-positive px-3 py-1.5 text-sm font-medium text-bg hover:bg-positive/90 disabled:opacity-50"
                  >
                    Approve
                  </button>
                  <button
                    onClick={startCorrect}
                    disabled={pending}
                    className="rounded border border-border-strong px-3 py-1.5 text-sm hover:bg-surface-raised disabled:opacity-50"
                  >
                    Correct
                  </button>
                  <button
                    onClick={startReject}
                    disabled={pending}
                    className="rounded border border-negative/40 px-3 py-1.5 text-sm text-negative hover:bg-negative/10 disabled:opacity-50"
                  >
                    Reject
                  </button>
                </div>
              )}
            </>
          )}

          <div className="mt-4 flex justify-between border-t border-border pt-3">
            <button
              onClick={() => goTo(index - 1)}
              disabled={index === 0}
              className="text-sm text-ink-muted hover:text-ink disabled:opacity-30"
            >
              ← previous
            </button>
            <button
              onClick={() => goTo(index + 1)}
              disabled={index === visibleFacts.length - 1}
              className="text-sm text-ink-muted hover:text-ink disabled:opacity-30"
            >
              next →
            </button>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-surface p-4">
          <h3 className="text-xs font-medium uppercase tracking-wide text-ink-muted">
            Source paragraph{current.source_paragraph_ids.length > 1 ? "s" : ""}
          </h3>
          <div className="mt-2 space-y-3">
            {current.source_paragraph_ids.map((pid) => {
              const paragraph = paragraphs[pid];
              return (
                <div key={pid} className="rounded border border-border p-3">
                  <div className="mb-1.5 flex items-center justify-between text-xs text-ink-muted">
                    <span className="font-mono">{pid}</span>
                    {paragraph && <span>{paragraph.section_key.replace(/_/g, " ")}</span>}
                  </div>
                  <p className="text-sm leading-relaxed">
                    {paragraph ? renderHighlighted(paragraph.text, quotes) : "(paragraph not found)"}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
