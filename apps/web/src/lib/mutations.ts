import "server-only";

import { query } from "./db";
import type { FactType } from "./types";

const TABLE_BY_TYPE: Record<FactType, string> = {
  Event: "events",
  Proposal: "proposals",
  ValuationAnalysis: "valuations",
};

// Whitelisted per record type -- "Correct" edits come from a form, and
// even though this module only runs in trusted server code, a fixed
// column whitelist means a field name can never be used to touch a
// column (id, run_id, content_hash, review_status itself) that isn't
// meant to be hand-edited here.
const EDITABLE_FIELDS: Record<FactType, string[]> = {
  Event: ["date_text", "date_start", "date_end", "date_precision", "event_type", "parties", "summary"],
  Proposal: [
    "date_text",
    "date_resolved",
    "proposer",
    "recipient",
    "price_low",
    "price_high",
    "premium_pct",
    "currency",
    "consideration_type",
    "proposal_kind",
    "status",
  ],
  ValuationAnalysis: [
    "advisor",
    "method",
    "metric",
    "multiple_low",
    "multiple_high",
    "implied_price_low",
    "implied_price_high",
    "key_assumptions",
  ],
};

export async function approveFact(factType: FactType, id: string): Promise<void> {
  const table = TABLE_BY_TYPE[factType];
  await query(`UPDATE ${table} SET review_status = 'confirmed' WHERE id = $1`, [id]);
}

export async function rejectFact(factType: FactType, id: string, note: string): Promise<void> {
  const table = TABLE_BY_TYPE[factType];
  await query(`UPDATE ${table} SET review_status = 'rejected', reviewer_note = $2 WHERE id = $1`, [
    id,
    note,
  ]);
}

export async function correctFact(
  factType: FactType,
  id: string,
  fields: Record<string, unknown>,
  note: string | null
): Promise<void> {
  const table = TABLE_BY_TYPE[factType];
  const allowed = EDITABLE_FIELDS[factType];
  const entries = Object.entries(fields).filter(([key]) => allowed.includes(key));

  const setClauses = entries.map(([key], i) => `${key} = $${i + 2}`);
  setClauses.push(`review_status = 'confirmed'`);
  if (note !== null) setClauses.push(`reviewer_note = $${entries.length + 2}`);

  const params: unknown[] = [id, ...entries.map(([, value]) => value)];
  if (note !== null) params.push(note);

  await query(`UPDATE ${table} SET ${setClauses.join(", ")} WHERE id = $1`, params);
}
