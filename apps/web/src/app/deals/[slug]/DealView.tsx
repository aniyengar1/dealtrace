"use client";

import { useState } from "react";
import type { EventRow, Fact, ParagraphRow, ProposalRow, ValuationRow } from "@/lib/types";
import { BidChart } from "./BidLadderChart";
import { HorizontalTimeline } from "./HorizontalTimeline";
import { Timeline } from "./Timeline";
import { ValuationPanel, hasPlottableValuations } from "./ValuationPanel";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { PartiesPanel } from "./PartiesPanel";
import { ChartNote } from "@/components/ui/ChartNote";

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
  const showValuationSection = hasPlottableValuations(valuations);

  return (
    <div className="space-y-10">
      <section id="timeline">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Process timeline</h2>
        <ChartNote
          definition="Every dated event in the sale process, grouped into six lanes by what kind of step it was."
          source="event records extracted from the deal's SEC merger-proxy filing"
        />
        <div className="mt-3">
          <HorizontalTimeline events={events} onInspect={setSelected} />
        </div>
        <div className="mt-4 rounded-lg border border-border bg-surface p-4">
          <Timeline events={events} onInspect={setSelected} />
        </div>
      </section>

      <section id="bids">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">Bids over time</h2>
        <ChartNote
          definition="Price per share offered by each bidder, in the order proposals were made, through to the signed deal price."
          source="proposal records extracted from the deal's SEC merger-proxy filing"
        />
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

      {showValuationSection ? (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-muted">
            Valuation vs. final price
          </h2>
          <ChartNote
            definition="Each financial advisor's implied per-share valuation range, compared with the price the deal actually signed at."
            source="valuation-analysis records extracted from the deal's fairness-opinion filing"
          />
          <div className="mt-3 rounded-lg border border-border bg-surface p-4">
            <ValuationPanel valuations={valuations} finalPrice={finalPrice} onInspect={setSelected} />
          </div>
        </section>
      ) : (
        // No full section header/description for the ~99% of deals
        // with no fairness-opinion valuation extracted at all -- that's
        // not a rendering bug, just a real data gap (most of this
        // dataset's filings never had one to extract), so a short note
        // in place of the chart is more honest than a section that
        // always renders but almost never has anything in it.
        <p className="text-sm text-ink-faint">No valuation analysis extracted from this filing to compare against the final price.</p>
      )}

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
