import type { Metadata } from "next";
import Link from "next/link";
import { Container } from "@/components/ui/Container";
import { Card } from "@/components/ui/Card";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";
import { getIncludedDealsSummary } from "@/lib/homeStats";
import { StepDiagram, type StepKind } from "./StepDiagram";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Methodology",
  description:
    "How DealTrace extracts, validates, and sources every fact on this site from SEC merger-proxy filings.",
};

const PIPELINE_STEPS: { kind: StepKind; title: string; body: string }[] = [
  { kind: "discover", title: "Discover", body: "EDGAR's quarterly form.idx files are scanned for DEFM14A, PREM14A, SC 14D9, SC TO-T, and S-4 filings, grouped into candidate deals by target CIK and filing date." },
  { kind: "classify", title: "Classify", body: "A no-LLM pass reads each filing's SIC code and document text to separate real operating-company M&A from SPAC/de-SPAC mechanics and other non-M&A filings (debt exchanges, reorganizations, going-private squeeze-outs)." },
  { kind: "extract", title: "Section + extract", body: "The “Background of the Merger” narrative and fairness-opinion sections are isolated, then an LLM reads them and returns structured events, proposals, and valuation analyses, never free text." },
  { kind: "validate", title: "Validate", body: "Every record is checked against the filing's own text before anyone sees it: quotes must appear verbatim (after normalization), numbers must appear in a cited quote, and dates are resolved by code, never by the model." },
  { kind: "load", title: "Load + review", body: "Validated records land in Postgres keyed to their source paragraphs. A human reviewer can confirm, correct, or reject any fact; review status is tracked but never blocks a fact from showing, just from being presented as verified." },
];

const DISCOVERY_FUNNEL: { label: string; count: number }[] = [
  { label: "Candidate filings", count: 3388 },
  { label: "Public-company acquisitions", count: 1607 },
  { label: "Extracted", count: 1174 },
  { label: "Unique deals (after de-duplication)", count: 964 },
];

const FINAL_FUNNEL_STEP_LABEL =
  "Target-side sale processes (after excluding buyer-side filings, spin-offs, affiliated mergers)";

const EXTRACTED_FIELDS: { type: string; fields: string }[] = [
  { type: "Event", fields: "date (as written + resolved), event type, parties involved, a one-sentence summary" },
  { type: "Proposal", fields: "date, proposer/recipient, price range, premium %, consideration type, proposal kind, status (open/accepted/rejected/superseded/withdrawn)" },
  { type: "ValuationAnalysis", fields: "advisor, method (trading comps / precedent transactions / DCF), multiple range, implied price range, key assumptions" },
];

const VALIDATION_RULES = [
  {
    title: "Quote matching",
    body: "Every source_quote must appear, after normalizing quote marks, dashes, and whitespace runs, somewhere in the paragraph it cites. Case is never folded; a quote has to match the filing's actual capitalization, not an approximation of it.",
  },
  {
    title: "Number checks",
    body: "Every number a record reports (a price, a multiple, a premium) has to appear in at least one of its own cited quotes. Low/high pairs are checked for correct ordering.",
  },
  {
    title: "Code-based date resolution",
    body: "Dates are never resolved by the model. If a record's own date text contains an absolute “Month Day, Year” date, that's used, full stop. A relative phrase (“later that day”) resolves to the nearest preceding absolute date in the same excerpt, by code. Anything else (a bare month, a shared-year day list) is left at its original precision rather than guessed.",
  },
];

const ACCURACY_ROWS: {
  deal: string;
  set: string;
  metric: string;
  result: string;
  pending?: boolean;
}[] = [
  { deal: "Splunk · Cisco", set: "Development", metric: "Core events & proposals vs. gold answer key", result: "100%" },
  { deal: "Zendesk · Consortium", set: "Held-out", metric: "Core-event recall / proposal recall", result: "97% / 100%" },
  { deal: "20-deal spot check (round 3)", set: "Bulk extraction sample", metric: "Field-by-field manual verification", result: "81 / 90 fields" },
  { deal: "20-deal spot check (round 4)", set: "Bulk extraction sample, 9 fields", metric: "Verified against the filing, with quotes", result: "136 / 180 fields" },
];

export default async function MethodologyPage() {
  const { count: nIncluded, minSigningYear } = await getIncludedDealsSummary();
  const since = minSigningYear ?? 2021;
  const funnel = [...DISCOVERY_FUNNEL, { label: FINAL_FUNNEL_STEP_LABEL, count: nIncluded }];

  return (
    <div>
      <Container wide className="relative py-14">
      <Reveal>
        <SectionHeading
          eyebrow="Methodology"
          title="How a filing becomes a sourced timeline"
          description="Every number on this site traces back through this pipeline to a specific sentence in a specific SEC filing. This page describes each stage honestly, including where it's still thin."
        />
      </Reveal>

      <section className="mt-12">
        <Reveal>
          <h2 className="inline-block rounded-lg bg-bg/90 px-4 py-2 text-lg font-semibold text-ink backdrop-blur-sm">Pipeline</h2>
        </Reveal>
        <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {PIPELINE_STEPS.map((step, i) => (
            <div key={step.title} className="relative">
              <Card className="h-full p-4">
                <StepDiagram kind={step.kind} step={i + 1} />
                <h3 className="mt-2 text-sm font-semibold text-ink">{step.title}</h3>
                <p className="mt-1.5 text-sm text-ink-muted">{step.body}</p>
              </Card>
              {i < PIPELINE_STEPS.length - 1 && (
                <span className="absolute -right-3 top-1/2 hidden -translate-y-1/2 text-ink-faint lg:block">→</span>
              )}
            </div>
          ))}
        </div>
        <p className="mt-3 inline-block rounded-lg bg-bg/90 px-4 py-2 text-sm text-ink-muted backdrop-blur-sm">
          Extracted with gemini-3.6-flash via Vertex AI; the model retires Jan 28, 2027; raw model outputs are
          archived.
        </p>
      </section>

      <section className="mt-14">
        <Reveal>
          <h2 className="inline-block rounded-lg bg-bg/90 px-4 py-2 text-lg font-semibold text-ink backdrop-blur-sm">Discovery funnel</h2>
        </Reveal>
        <Reveal delay={60}>
          <div className="mt-5 grid gap-3 sm:grid-cols-5">
            {funnel.map((step, i) => (
              <div key={step.label} className="relative">
                <Card className="h-full p-4">
                  <span className="font-serif text-2xl text-accent tabular-nums">{step.count.toLocaleString()}</span>
                  <p className="mt-1.5 text-sm text-ink-muted">{step.label}</p>
                </Card>
                {i < funnel.length - 1 && (
                  <span className="absolute -right-3 top-1/2 hidden -translate-y-1/2 text-ink-faint sm:block">→</span>
                )}
              </div>
            ))}
          </div>
        </Reveal>
        <p className="mt-3 inline-block rounded-lg bg-bg/90 px-4 py-2 text-sm text-ink-muted backdrop-blur-sm">
          De-duplication (<code className="text-ink">src/dedup_deals.py</code>) resolves cases where the same
          underlying deal surfaces as two or more separately discovered filings: a target company
          refiling an amended proxy, or a tender offer and a merger-proxy for the same transaction both getting
          picked up by discovery. Matches are grouped by target entity and announcement window; one deal in each
          group is marked canonical (<code className="text-ink">is_canonical</code>), the rest point to it via{" "}
          <code className="text-ink">duplicate_of</code> and are excluded from every count and statistic on this
          site.
        </p>
      </section>

      <section className="mt-14">
        <Reveal>
          <h2 className="inline-block rounded-lg bg-bg/90 px-4 py-2 text-lg font-semibold text-ink backdrop-blur-sm">What&apos;s extracted</h2>
        </Reveal>
        <Reveal delay={60}>
          <div className="mt-5 overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-surface text-xs uppercase tracking-wide text-ink-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Record type</th>
                  <th className="px-4 py-2.5 font-medium">Fields</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {EXTRACTED_FIELDS.map((row) => (
                  <tr key={row.type}>
                    <td className="px-4 py-3 font-medium text-ink">{row.type}</td>
                    <td className="px-4 py-3 text-ink-muted">{row.fields}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Reveal>
        <p className="mt-3 inline-block rounded-lg bg-bg/90 px-4 py-2 text-sm text-ink-muted backdrop-blur-sm">
          Every record also carries its 1–3 source quotes, the paragraph(s) they came from, a pass/fail
          validation flag, and a review status, visible on each deal page via the evidence drawer.
        </p>
      </section>

      <section className="mt-14">
        <Reveal>
          <h2 className="inline-block rounded-lg bg-bg/90 px-4 py-2 text-lg font-semibold text-ink backdrop-blur-sm">Validation rules</h2>
        </Reveal>
        <div className="mt-5 grid gap-5 sm:grid-cols-3">
          {VALIDATION_RULES.map((rule) => (
            <Card key={rule.title} className="h-full p-4">
              <h3 className="text-sm font-semibold text-ink">{rule.title}</h3>
              <p className="mt-2 text-sm text-ink-muted">{rule.body}</p>
            </Card>
          ))}
        </div>
      </section>

      <section className="mt-14">
        <Reveal>
          <div className="inline-block max-w-2xl rounded-lg bg-bg/90 px-5 py-4 backdrop-blur-sm">
            <h2 className="text-lg font-semibold text-ink">Accuracy</h2>
            <p className="mt-2 text-sm text-ink-muted">
              Measured by scoring an extraction run against a hand-checked gold answer key read directly off the
              filing (see <code className="text-ink">src/score.py</code>). A held-out deal is one whose gold key was
              never consulted while the extraction prompt was being developed.
            </p>
            <p className="mt-3 text-sm text-ink-muted">
              Accuracy was audited in four rounds of 20 randomly sampled deals, each checked field-by-field against
              the source filing by an independent model (Claude) with all flagged fields reviewed by the author.
              Rounds 1–2 found systematic errors (buyer-side filings mislabeled as sales, inflated bidder counts,
              wrong first-contact dates), fixed with deterministic rules. Round 3, on a fresh sample: 18 of 20 deals
              were genuine target-side sale processes; across those, 81 of 90 extracted fields were correct or
              materially correct, 9 were wrong, most often first-contact dates, which are therefore excluded from
              headline statistics. Known limitations: some acquirers remain unresolved (&ldquo;Undisclosed&rdquo;),
              and stock-for-stock deals have no per-share cash price.
            </p>
            <p className="mt-3 text-sm text-ink-muted">
              Round 4, a fresh sample of 20 deals across 9 fields each (180 total), verified directly against the
              signed filing with exact quotes: 136 fields (76%) correct or materially correct, 28 (16%) wrong, and
              16 (9%) where no unique, defensible answer could be established from the filing at all (most often a
              same-date tie between two bidders&apos; initial proposals). The wrong/unverifiable fields drove six
              deterministic (no-LLM) fixes, re-run across the full public dataset (793 deals, after the deal-type
              correction below):
            </p>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-ink-muted">
              <li>
                <span className="text-ink">Consideration type.</span> A deal whose extracted proposal never
                resolved a cash/stock/mixed type is now backfilled, when safe, from the signed agreement&apos;s own
                &ldquo;you will receive $X.XX in cash&rdquo;/&ldquo;N shares of [Acquirer]&rdquo; clause. 76 of 793
                deals had an unresolved type; 28 were newly resolved this way (76 → 48 unresolved), each spot
                -checked against its own filing quote.
              </li>
              <li>
                <span className="text-ink">Final price.</span> The &ldquo;final&rdquo; proposal now prefers the
                latest still-open proposal over a later-dated proposal nobody accepted (a rival bidder&apos;s
                unsolicited, rejected, or withdrawn counter could otherwise outrank the real deal&apos;s own
                standing terms purely by date — Vista Outdoor&apos;s reported price was briefly MNC&apos;s
                unsolicited, never-accepted bid). 14 of 793 deals changed, which also corrects which bidder is
                credited as the winner for 7 of those (the &ldquo;final&rdquo; proposer is what the first-bidder
                -wins comparison checks against). Deals whose signed consideration is a base-cash amount plus a
                separate, contingent Contingent Value Right (CVR) are now excluded from the % price-bump stat,
                since the CVR&apos;s payout is unknown at signing (19 of 793 newly excluded).
              </li>
              <li>
                <span className="text-ink">First-bidder ties.</span> When two or more distinct bidders&apos;
                earliest proposals land on the same date, which one was first is genuinely undefined (the
                underlying data has no reliable same-day ordering) — these deals are now excluded from the
                first-bidder-wins stat rather than resolved by an arbitrary tie-break. 50 of 793 deals excluded;
                the all-deals rate is now 64% (n=717), and the contested-deals (2+ bidders) rate is 42% (n=442).
              </li>
              <li>
                <span className="text-ink">Consortium winner matching.</span> A deal&apos;s stored acquirer is
                sometimes just a generic label (&ldquo;Consortium&rdquo;) that doesn&apos;t string-match the named
                members who actually made the winning proposal. The fix resolves a generic label to the fuller
                joint name the filing&apos;s own narrative already uses elsewhere in the same deal. 2 deals flip
                from &ldquo;first bidder lost&rdquo; to &ldquo;first bidder won&rdquo;: Option Care Health and
                Atlas Air Worldwide, whose June 2021 consortium made the first offer and is the eventual buyer
                group.
              </li>
              <li>
                <span className="text-ink">Deal type.</span> &ldquo;Merger of equals&rdquo; detection, previously
                S-4-only, now also covers DEFM14A/PREM14A joint proxies (AvalonBay/Equity Residential, Veeco/Axcelis).
                Widening the gate alone first jumped this from 14 to 78 of 962 canonical deals with extracted data
                (a broader base than the 802 above, since a deal&apos;s type itself determines whether it counts
                toward that 802) -- but a pre-release spot-check of those 64 newly-caught deals found 46 were a
                rejected alternative, a hedged exploratory discussion, a fairness-opinion comps-screen exclusion, or
                a reference to an unrelated transaction, not the signed deal&apos;s own structure (ConocoPhillips/
                Marathon Oil: &ldquo;Party B&rdquo;, a different, non-acquiring bidder, proposed the merger of
                equals; Rio Tinto/Arcadium Lithium: a reference to Arcadium&apos;s own prior, unrelated formation).
                The same check against the original 14 found 7 more pre-existing false positives. Tightened to
                require a definite structural statement about the transaction itself (&ldquo;will combine...in a
                merger of equals&rdquo;, &ldquo;structured as a merger of equals&rdquo;), the final count is 14 → 24
                of 962. Vista Outdoor&apos;s sale is now excluded as a complex, multi-part structure (a Sporting
                Products sale to CSG plus a separate
                Revelyst spin-off) rather than counted as a plain acquisition.
              </li>
              <li>
                <span className="text-ink">Signing date.</span> Now prefers the original merger agreement date over
                a later amendment or a press-release announcement date (Verde Bio/SSTC: Dec 11, 2023, not the Feb 8
                amendment; Marel/JBT: Apr 4 agreement, not the Apr 5 announcement). 27 of 793 deals had their
                resolved signing date move, almost always earlier.
              </li>
            </ul>
            <p className="mt-3 text-sm text-ink-muted">
              Known gap: two deals (Verona Pharma/Merck, GW Pharma/Jazz) price their consideration per American
              Depositary Share, a multiple of the true per-ordinary-share economic value (Verona: $107 per ADS = 8
              ordinary shares, i.e. $13.375 per ordinary share) — the stored figure is the per-ADS price exactly as
              the filing states it, not yet converted or labeled by unit on this site.
            </p>
          </div>
        </Reveal>
        <Reveal delay={60}>
          <div className="mt-5 overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-surface text-xs uppercase tracking-wide text-ink-muted">
                <tr>
                  <th className="px-4 py-2.5 font-medium">Deal</th>
                  <th className="px-4 py-2.5 font-medium">Set</th>
                  <th className="px-4 py-2.5 font-medium">Metric</th>
                  <th className="px-4 py-2.5 font-medium">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {ACCURACY_ROWS.map((row) => (
                  <tr key={row.deal}>
                    <td className="px-4 py-3 font-medium text-ink">{row.deal}</td>
                    <td className="px-4 py-3 text-ink-muted">{row.set}</td>
                    <td className="px-4 py-3 text-ink-muted">{row.metric}</td>
                    <td className={`px-4 py-3 tabular-nums ${row.pending ? "text-ink-faint italic" : "text-accent"}`}>
                      {row.result}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Reveal>
      </section>

      <section className="mt-14">
        <Reveal>
          <h2 className="inline-block rounded-lg bg-bg/90 px-4 py-2 text-lg font-semibold text-ink backdrop-blur-sm">Coverage</h2>
          <Card className="mt-5 p-5 text-sm text-ink-muted">
            <p>
              <span className="text-ink">Date range:</span> deals announced {since} onward (bounded by when the
              pipeline&apos;s automated EDGAR discovery starts looking).
            </p>
            <p className="mt-2">
              <span className="text-ink">Form types:</span> DEFM14A, PREM14A, SC 14D9, SC TO-T, and S-4, the
              merger-proxy and tender-offer filings that carry a “Background of the Merger” narrative.
            </p>
            <p className="mt-2">
              <span className="text-ink">Excluded:</span> SPAC/de-SPAC business combinations (classified and
              dropped before extraction; they don&apos;t have a comparable sale-process narrative), and filings
              whose background section a parser can&apos;t reliably isolate (logged, not silently skipped).
            </p>
            <p className="mt-2">
              <span className="text-ink">Also excluded from the headline stats</span> (but still extracted and
              shown on the deal&apos;s own page): a holdco-structured merger of equals, a manager-internalization
              or affiliated-manager merger, a governance-body-as-acquirer deal, a self-reorganization, a spin-off,
              an S-4 whose vote direction can&apos;t be determined, and a complex, multi-part structure (Vista
              Outdoor). A plain &ldquo;merger of equals&rdquo; or reverse merger is NOT excluded -- both count
              toward the stats the same as an ordinary acquisition.
            </p>
          </Card>
        </Reveal>
      </section>

      <section className="mt-14 mb-4">
        <Reveal>
          <h2 className="inline-block rounded-lg bg-bg/90 px-4 py-2 text-lg font-semibold text-ink backdrop-blur-sm">Known limitations</h2>
          <Card className="mt-5 p-5 text-sm text-ink-muted">
            <ul className="list-disc space-y-2 pl-5">
              <li>
                Every fact shown is machine-verified against a quote from its filing before it&apos;s loaded, but
                human review of bulk-extracted deals is still in progress behind the scenes; a figure can be
                accurate to its source quote and still reflect a model misreading of that quote.
              </li>
              <li>
                Automated deal discovery and classification is best-effort: the same underlying filing can
                occasionally surface as two separately tracked deals before de-duplication catches up.
              </li>
              <li>
                &ldquo;Days to signing,&rdquo; &ldquo;bidders,&rdquo; and the first-to-final bump are derived from whichever events
                and proposals a given run extracted; a background section that omits an early contact will
                understate the real timeline, not just the recorded one.
              </li>
              <li>
                Valuation analyses are only as complete as each filing&apos;s fairness-opinion section; not every deal
                has one.
              </li>
              <li>
                Some filings redact a losing bidder&apos;s identity during an active sale process (&ldquo;Party A,&rdquo;
                &ldquo;Company B,&rdquo; &ldquo;Bidder 1&rdquo;); DealTrace reports these anonymized labels exactly as the filing
                states them, rather than guessing a real name.
              </li>
            </ul>
          </Card>
        </Reveal>
      </section>

      <p className="inline-block rounded-lg bg-bg/90 px-4 py-2 text-sm text-ink-muted backdrop-blur-sm">
        <Link href="/" className="text-accent hover:underline">
          ← Back to home
        </Link>
      </p>
      </Container>
    </div>
  );
}
