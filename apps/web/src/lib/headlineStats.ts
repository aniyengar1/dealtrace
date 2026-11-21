import "server-only";

import { query } from "./db";

// headline_stats: one row per named cross-deal statistic, computed by
// the pipeline (src/bulk_stats.py) over canonical deals and written
// straight to this table -- the authoritative source for every
// cross-deal number this site shows. Distribution stats (parties
// contacted, bidders, proposals, pct-increase, days-to-signing) carry
// the full n/p25/median/p75/min/max; the one scalar stat
// (pct_first_bidder_is_eventual_acquirer, a plain percentage) only ever
// populates `median`.
// days_first_contact_to_signing is deliberately excluded -- a round-3
// spot-check found it the least reliable extracted field (5 of 9
// errors were first-contact dates), so it's never published to
// headline_stats or shown anywhere on the site. See src.bulk_stats's
// compute_all().
export type HeadlineStatName =
  | "parties_contacted"
  | "bidders_who_submitted_a_proposal"
  | "proposals_per_deal"
  | "pct_increase_cash_deals"
  | "pct_first_bidder_is_eventual_acquirer"
  | "days_first_proposal_to_signing";

export interface HeadlineStatRow {
  name: HeadlineStatName;
  n: number;
  p25: number | null;
  median: number | null;
  p75: number | null;
  min: number | null;
  max: number | null;
  exclusions: Record<string, unknown>;
  generatedAt: string;
  codeCommit: string;
}

export async function getHeadlineStats(): Promise<Record<HeadlineStatName, HeadlineStatRow | undefined>> {
  const rows = await query<{
    name: HeadlineStatName;
    n: number;
    p25: number | null;
    median: number | null;
    p75: number | null;
    min: number | null;
    max: number | null;
    exclusions: Record<string, unknown>;
    generated_at: string;
    code_commit: string;
  }>(`SELECT name, n, p25, median, p75, min, max, exclusions, generated_at, code_commit FROM headline_stats`);

  const byName = {} as Record<HeadlineStatName, HeadlineStatRow | undefined>;
  for (const r of rows) {
    byName[r.name] = {
      name: r.name,
      n: r.n,
      p25: r.p25,
      median: r.median,
      p75: r.p75,
      min: r.min,
      max: r.max,
      exclusions: r.exclusions,
      generatedAt: r.generated_at,
      codeCommit: r.code_commit,
    };
  }
  return byName;
}
