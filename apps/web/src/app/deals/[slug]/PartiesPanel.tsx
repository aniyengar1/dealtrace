import type { EventRow, ProposalRow } from "@/lib/types";

type Role = "Target" | "Acquirer" | "Other bidder" | "Mentioned party";

function roleOf(name: string, target: string, acquirer: string, bidders: Set<string>): Role {
  if (name === target) return "Target";
  if (name === acquirer) return "Acquirer";
  if (bidders.has(name)) return "Other bidder";
  return "Mentioned party";
}

const ROLE_ORDER: Role[] = ["Target", "Acquirer", "Other bidder", "Mentioned party"];

// Every named party that shows up in an event or a proposal, grouped by
// the role the data itself implies -- never a hand-maintained map of
// who's an advisor vs. a bidder, since that isn't extracted today.
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

  const names = new Set<string>([target, acquirer]);
  for (const e of events) for (const p of e.parties) names.add(p);
  for (const p of proposals) {
    names.add(p.proposer);
    names.add(p.recipient);
  }

  const byRole = new Map<Role, string[]>();
  for (const name of names) {
    const role = roleOf(name, target, acquirer, bidders);
    const list = byRole.get(role) ?? [];
    list.push(name);
    byRole.set(role, list);
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {ROLE_ORDER.filter((r) => byRole.has(r)).map((role) => (
        <div key={role}>
          <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">{role}</p>
          <ul className="mt-1.5 space-y-1 text-sm text-ink">
            {byRole
              .get(role)!
              .sort()
              .map((name) => (
                <li key={name}>{name}</li>
              ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
