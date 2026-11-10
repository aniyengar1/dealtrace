"use client";

import { useMemo, useState } from "react";
import type { EventRow, Fact, ParagraphRow, ProposalRow, ValuationRow } from "@/lib/types";
import { BidChart } from "./BidChart";
import { Timeline } from "./Timeline";
import { ValuationPanel } from "./ValuationPanel";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { ReviewProgressBanner } from "@/components/StatusBadge";

export function DealView({
  target,
  finalPrice,
  events,
  proposals,
  valuations,
  paragraphs,
}: {
  target: string;
  finalPrice: number | null;
  events: EventRow[];
  proposals: ProposalRow[];
  valuations: ValuationRow[];
  paragraphs: Record<string, ParagraphRow>;
}) {
  const [selected, setSelected] = useState<Fact | null>(null);

  const { reviewed, total } = useMemo(() => {
    const all = [...events, ...proposals, ...valuations];
    return { reviewed: all.filter((f) => f.review_status !== "unreviewed").length, total: all.length };
  }, [events, proposals, valuations]);

  return (
    <div className="space-y-8">
      <ReviewProgressBanner reviewed={reviewed} total={total} />

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">Bids over time</h2>
        <div className="mt-3">
          <BidChart proposals={proposals} events={events} target={target} onInspect={setSelected} />
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">Timeline</h2>
        <div className="mt-3 rounded-lg border border-neutral-200 bg-white p-4">
          <Timeline events={events} onInspect={setSelected} />
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">
          Valuation vs. final price
        </h2>
        <div className="mt-3 rounded-lg border border-neutral-200 bg-white p-4">
          <ValuationPanel valuations={valuations} finalPrice={finalPrice} onInspect={setSelected} />
        </div>
      </section>

      <EvidenceDrawer fact={selected} paragraphs={paragraphs} onClose={() => setSelected(null)} />
    </div>
  );
}
