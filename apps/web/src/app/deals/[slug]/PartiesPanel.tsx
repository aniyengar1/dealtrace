import type { EventRow, ProposalRow } from "@/lib/types";

type Group = "Bidders" | "Advisors & banks" | "Legal counsel" | "People" | "Other";

const GROUP_ORDER: Group[] = ["Bidders", "Advisors & banks", "Legal counsel", "People", "Other"];

// Heuristic only -- nothing in the data model tags a mentioned party as
// "advisor" or "counsel" (events/proposals just carry a flat parties
// list), so this infers a group from naming conventions the same way
// buyerType() infers strategic/sponsor from an acquirer name. "LLP" is
// close to a hard rule for US law firms; the bank/advisor list covers
// the handful of names that show up across unrelated deals (Qatalyst,
// the bulge-bracket banks) plus the generic "Partners/Capital/
// Securities" pattern. Anything with a corporate suffix but no match
// falls to "Other" rather than a guess; anything with no corporate
// suffix at all is assumed to be a named individual ("People").
const LAW_FIRM_RE = /\bLLP\b/i;
const ADVISOR_RE =
  /\b(Partners|Capital|Securities|Advisors?|Advisory|Qatalyst|Centerview|Evercore|Lazard|Moelis|Houlihan Lokey|Perella Weinberg|Allen & Company|Goldman Sachs|Morgan Stanley|J\.?P\.?\s?Morgan|Bank of America|Barclays|Wells Fargo|UBS|Jefferies|Citigroup|Citi|Deutsche Bank|RBC|Credit Suisse|William Blair|Raymond James|Stifel|Guggenheim)\b/i;
const ORG_SUFFIX_RE = /\b(Inc|Corp(oration)?|L\.?L\.?C\.?|Ltd|Limited|Company|Co\.|Group|N\.A\.|plc|AG|SA|Holdings?)\b\.?/i;

function groupOf(name: string, bidders: Set<string>): Group {
  if (bidders.has(name)) return "Bidders";
  if (LAW_FIRM_RE.test(name)) return "Legal counsel";
  if (ADVISOR_RE.test(name)) return "Advisors & banks";
  if (ORG_SUFFIX_RE.test(name)) return "Other";
  return "People";
}

// Every named party that shows up in an event or a proposal, grouped by
// an inferred role -- never a hand-maintained map of who's an advisor
// vs. a bidder, since that isn't extracted today. Target/acquirer get
// top billing (they're already the page's headline); every other name
// sorts into one of the five role groups below, collapsed by default
// since a deal with a dozen law firms and banks shouldn't dominate the
// page before a reader has even looked at the timeline.
export function PartiesPanel({
  target,
  acquirer,
  events,
  proposals,
}: {
  target: string;
  acquirer: string;
  events: EventRow[];
  proposals: ProposalRow[];
}) {
  const bidders = new Set(proposals.map((p) => p.proposer).filter((p) => p !== target));

  const names = new Set<string>();
  for (const e of events) for (const p of e.parties) names.add(p);
  for (const p of proposals) {
    names.add(p.proposer);
    names.add(p.recipient);
  }
  names.delete(target);
  names.delete(acquirer);

  const byGroup = new Map<Group, string[]>();
  for (const name of names) {
    const group = groupOf(name, bidders);
    const list = byGroup.get(group) ?? [];
    list.push(name);
    byGroup.set(group, list);
  }

  return (
    <div>
      <dl className="flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-ink-muted">Target</dt>
          <dd className="text-ink">{target}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium uppercase tracking-wide text-ink-muted">Acquirer</dt>
          <dd className="text-ink">{acquirer}</dd>
        </div>
      </dl>

      <div className="mt-4 space-y-2">
        {GROUP_ORDER.filter((g) => byGroup.has(g)).map((group) => {
          const list = byGroup.get(group)!.sort();
          return (
            <details key={group} className="group rounded-lg border border-border bg-surface px-3 py-2">
              <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium text-ink marker:content-none">
                <span>
                  {group} <span className="tabular-nums text-ink-muted">({list.length})</span>
                </span>
                <span className="text-ink-faint transition-transform group-open:rotate-180">⌄</span>
              </summary>
              <ul className="mt-2 space-y-1 border-t border-border pt-2 text-sm text-ink-muted">
                {list.map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            </details>
          );
        })}
      </div>
    </div>
  );
}
