import type { ReactNode } from "react";

// Mirrors validate.py's normalize_for_match exactly: quote/dash variants
// and whitespace runs are the only things source_quotes can legitimately
// differ from the paragraph text on (that's what passing validation
// means) -- case is never folded on either side. JS's \s already matches
// NBSP, so collapsing whitespace runs covers that case for free.
const QUOTE_CLASS = `['"‘’‚′“”„″]`;
const DASH_CLASS = `[-‐‑‒–—―−]`;
const QUOTE_RE = new RegExp(QUOTE_CLASS);
const DASH_RE = new RegExp(DASH_CLASS);

function buildFuzzyQuoteRegex(quote: string): RegExp | null {
  if (!quote) return null;
  const pattern = quote
    .split("")
    .map((ch) => {
      if (QUOTE_RE.test(ch)) return QUOTE_CLASS;
      if (DASH_RE.test(ch)) return DASH_CLASS;
      if (/\s/.test(ch)) return "\\s+";
      return ch.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    })
    .join("")
    .replace(/(?:\\s\+)+/g, "\\s+");
  try {
    return new RegExp(pattern);
  } catch {
    return null;
  }
}

export interface QuoteSpan {
  start: number;
  end: number;
}

export function findQuoteSpans(text: string, quotes: string[]): QuoteSpan[] {
  const spans: QuoteSpan[] = [];
  for (const quote of quotes) {
    const regex = buildFuzzyQuoteRegex(quote);
    const match = regex?.exec(text);
    if (match) {
      spans.push({ start: match.index, end: match.index + match[0].length });
    }
  }
  spans.sort((a, b) => a.start - b.start);
  const merged: QuoteSpan[] = [];
  for (const span of spans) {
    const last = merged[merged.length - 1];
    if (last && span.start <= last.end) {
      last.end = Math.max(last.end, span.end);
    } else {
      merged.push({ ...span });
    }
  }
  return merged;
}

export function renderHighlighted(text: string, quotes: string[]): ReactNode[] {
  const spans = findQuoteSpans(text, quotes);
  if (spans.length === 0) return [text];
  const nodes: ReactNode[] = [];
  let cursor = 0;
  spans.forEach((span, i) => {
    if (span.start > cursor) nodes.push(text.slice(cursor, span.start));
    nodes.push(
      <mark key={i} className="rounded bg-amber-200 px-0.5 text-inherit">
        {text.slice(span.start, span.end)}
      </mark>
    );
    cursor = span.end;
  });
  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}
