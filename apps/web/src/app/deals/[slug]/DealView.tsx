"use client";

import { useState } from "react";
import type { EventRow, Fact, ParagraphRow, ProposalRow, ValuationRow } from "@/lib/types";
import { BidChart } from "./BidLadderChart";
import { HorizontalTimeline } from "./HorizontalTimeline";
import { Timeline } from "./Timeline";
import { ValuationPanel } from "./ValuationPanel";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { PartiesPanel } from "./PartiesPanel";

export function DealView({
  target,
  acquirer,
  finalPrice,
  finalPriceIsRatio = null,
  events,
  proposals,
  valuations,
  paragraphs,
  initialFact = null,
}: {
  target: string;
  acquirer: string;
  finalPrice: number | null;
  finalPriceIsRatio?: boolean | null;
  events: EventRow[];
  proposals: ProposalRow[];
  valuations: ValuationRow[];
  paragraphs: Record<string, ParagraphRow>;
  initialFact?: Fact | null;
}) {
  const [selected, setSelected] = useState<Fact | null>(initialFact);

  return (
    <div className="space-y-10">
      <section id="timeline">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Process timeline</h2>
        <div className="mt-3">
          <HorizontalTimeline events={events} onInspect={setSelected} />
        </div>
        <div className="mt-4 rounded-lg border border-border bg-surface p-4">
          <Timeline events={events} onInspect={setSelected} />
        </div>
      </section>

      <section id="bids">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Bids over time</h2>
        <div className="mt-3">
          <BidChart
            proposals={proposals}
            events={events}
            target={target}
            finalPrice={finalPrice}
            finalPriceIsRatio={finalPriceIsRatio}
            onInspect={setSelected}
          />
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
          Valuation vs. final price
        </h2>
        <div className="mt-3 rounded-lg border border-border bg-surface p-4">
          <ValuationPanel valuations={valuations} finalPrice={finalPrice} onInspect={setSelected} />
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Parties</h2>
        <div className="mt-3 rounded-lg border border-border bg-surface p-4">
          <PartiesPanel target={target} acquirer={acquirer} events={events} proposals={proposals} />
        </div>
      </section>

      <EvidenceDrawer fact={selected} paragraphs={paragraphs} onClose={() => setSelected(null)} />
    </div>
  );
}
