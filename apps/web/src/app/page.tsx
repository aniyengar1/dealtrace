import Link from "next/link";
import { listCanonicalDealMetrics, getDealMetricsBySlug, getLatestAddedDeal } from "@/lib/dealMetrics";
import { computeHomeStats } from "@/lib/homeStats";
import { getTickerDeals } from "@/lib/tickerDeals";
import { getDealBySlug, getLatestFactsRunForDeal, getEventsForRun, getProposalsForRun } from "@/lib/queries";
import { statDecimals, formatDate } from "@/lib/format";
import { dealTitle } from "@/lib/labels";
import { Container } from "@/components/ui/Container";
import { Card } from "@/components/ui/Card";
import { LinkButton } from "@/components/ui/Button";
import { StatNumber } from "@/components/ui/StatNumber";
import { ChartNote } from "@/components/ui/ChartNote";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";
import { BidChart as BidLadderChart } from "./deals/[slug]/BidLadderChart";
import { FeaturedDealCard } from "./FeaturedDealCard";
import { HeroMedia } from "./HeroMedia";
import { DealTicker } from "./DealTicker";
import { InsightBar } from "./InsightBar";

const FEATURED_DEAL_SLUG = "splunk";

export const dynamic = "force-dynamic";

const STEPS = [
  {
    title: "SEC filing",
    body: "A DEFM14A, SC 14D9, or S-4 merger proxy is fetched and cached from EDGAR.",
  },
  {
    title: "Extraction",
    body: "An LLM reads the “Background of the Merger” narrative and pulls out every event, proposal, and valuation analysis as structured records.",
  },
  {
    title: "Validation against source",
    body: "Every extracted fact is checked against the filing's own quoted text, dates, and numbers before it's trusted.",
  },
  {
    title: "Timeline",
    body: "Validated facts assemble into a sourced, navigable process timeline — click any claim to see the quote it came from.",
  },
];

const FEATURED_SLUGS = ["splunk", "zendesk", "activision", "mandiant", "citrix", "coupa"];

export default async function HomePage() {
  const [allCanonical, stats, tickerDeals, latestAdded, featuredDeal, featuredMetrics] = await Promise.all([
    listCanonicalDealMetrics(),
    computeHomeStats(),
    getTickerDeals(),
    getLatestAddedDeal(),
    getDealBySlug(FEATURED_DEAL_SLUG),
    getDealMetricsBySlug(FEATURED_DEAL_SLUG),
  ]);
  const featured = FEATURED_SLUGS.map((slug) => allCanonical.find((d) => d.slug === slug)).filter(
    (d): d is NonNullable<typeof d> => d !== undefined
  );
  const headlineCount = stats.nDealsCovered;

  // A live-rendered bid ladder for one well-known deal, right in the
  // hero, in place of the old aggregate histogram -- the point is to
  // show what the site actually extracts (a real negotiation), not
  // just a summary statistic, the moment someone lands on the page.
  const featuredFactsRun = featuredDeal ? await getLatestFactsRunForDeal(featuredDeal.id) : null;
  const [featuredEvents, featuredProposals] = featuredFactsRun
    ? await Promise.all([getEventsForRun(featuredFactsRun.id), getProposalsForRun(featuredFactsRun.id)])
    : [[], []];

  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border">
        <HeroMedia />
        <Container
          wide
          className="relative grid grid-cols-1 gap-10 py-20 sm:py-28 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:py-36"
        >
          <div className="relative">
            {/* Local gradient, not a page-wide darkening -- strong right
                behind the headline/subhead, fading to nothing past the
                text column, so the montage stays visible everywhere
                else in the hero. */}
            <div
              aria-hidden
              className="absolute -inset-x-6 -inset-y-10 -z-10 sm:-inset-x-10"
              style={{
                background:
                  "radial-gradient(60% 90% at 30% 40%, rgba(10,10,11,0.75) 0%, rgba(10,10,11,0.55) 45%, rgba(10,10,11,0.15) 75%, transparent 100%)",
              }}
            />
            <h1 className="font-serif text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
              <span className="text-accent-bright">{headlineCount} M&amp;A sale processes,</span>{" "}
              <span className="text-ink-muted">
                reconstructed from SEC filings &mdash; every fact linked to its source sentence.
              </span>
            </h1>
            <div className="mt-8 flex flex-wrap gap-3">
              <LinkButton href="/deals" variant="primary">
                Explore deals
              </LinkButton>
              <LinkButton href="/methodology" variant="secondary">
                How it works
              </LinkButton>
            </div>
            {latestAdded && (
              <p className="mt-6 font-mono text-xs text-ink-faint">
                Latest deal added: {dealTitle(latestAdded.acquirerDisplay, latestAdded.targetDisplay)}
                {latestAdded.signingDate ? ` · signed ${formatDate(latestAdded.signingDate)}` : ""}
              </p>
            )}
          </div>
          <Card className="p-5">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              {featuredDeal && featuredMetrics
                ? `Bid history: ${dealTitle(featuredMetrics.acquirerDisplay, featuredMetrics.targetDisplay)}`
                : "Bid history"}
            </p>
            <ChartNote
              definition="Price per share offered by each bidder, in the order proposals were made, through to the signed deal price."
              source="proposal records extracted from the deal's SEC merger-proxy filing"
            />
            {featuredMetrics && featuredProposals.length > 0 ? (
              <div className="mt-3">
                <BidLadderChart
                  proposals={featuredProposals}
                  events={featuredEvents}
                  target={featuredMetrics.targetDisplay}
                  finalPrice={featuredMetrics.finalPrice}
                  finalPriceIsRatio={featuredMetrics.finalPriceIsRatio}
                />
              </div>
            ) : (
              <p className="mt-3 text-sm text-ink-faint">Not enough priced proposals yet to chart.</p>
            )}
          </Card>
        </Container>
        {tickerDeals.length > 0 && (
          <div className="relative border-t border-border/60 bg-bg/70 py-3 backdrop-blur-sm">
            <DealTicker deals={tickerDeals} />
          </div>
        )}
      </section>

      {/* What the data says -- quick stats + narrative findings share one
          section, not two, so the page reads as hero -> findings ->
          how it works -> featured deals -> accuracy -> footer. */}
      <section className="border-b border-border py-20">
        <Container wide>
          <Reveal>
            <SectionHeading
              eyebrow="Findings"
              title="What the data says"
              description={`Three patterns across all ${headlineCount} deals, not just the well-known names.`}
            />
          </Reveal>
          <div className="mt-10 grid grid-cols-2 gap-8 sm:grid-cols-3">
            <StatNumber value={stats.nDealsCovered} label="Deals covered" size="lg" />
            {stats.medianBidders && (
              <StatNumber
                value={stats.medianBidders.value}
                decimals={statDecimals(stats.medianBidders.value)}
                label="Median distinct bidders per deal"
                n={stats.medianBidders.n}
                size="lg"
              />
            )}
            {stats.medianProposals && (
              <StatNumber
                value={stats.medianProposals.value}
                decimals={statDecimals(stats.medianProposals.value)}
                label="Median proposals per deal"
                n={stats.medianProposals.n}
                size="lg"
              />
            )}
          </div>
          <div className="mt-5 grid gap-5 sm:grid-cols-3">
            {stats.pctFirstBidderWon && (
              <Reveal>
                <Card className="p-5">
                  <InsightBar
                    value={stats.pctFirstBidderWon.value}
                    domain={[0, 100]}
                    valueLabel={`${stats.pctFirstBidderWon.value.toFixed(statDecimals(stats.pctFirstBidderWon.value))}%`}
                    domainLabels={["0%", "100%"]}
                    referenceAt={50}
                  />
                  <p className="mt-3 text-sm text-ink-muted">
                    The first bidder to show up wins the deal about half the time (n = {stats.pctFirstBidderWon.n}) —
                    showing up early is an edge, not a guarantee.
                  </p>
                </Card>
              </Reveal>
            )}
            {stats.medianPctBump && (
              <Reveal delay={80}>
                <Card className="p-5">
                  <InsightBar
                    value={stats.medianPctBump.value}
                    domain={[-25, 50]}
                    valueLabel={`${stats.medianPctBump.value >= 0 ? "+" : ""}${stats.medianPctBump.value.toFixed(statDecimals(stats.medianPctBump.value))}%`}
                    domainLabels={["-25%", "+50%"]}
                    referenceAt={0}
                  />
                  <p className="mt-3 text-sm text-ink-muted">
                    Cash deals typically sign for about {stats.medianPctBump.value.toFixed(1)}% more than the first
                    priced proposal (n = {stats.medianPctBump.n}) — negotiation usually moves the price, not just the
                    terms.
                  </p>
                </Card>
              </Reveal>
            )}
            {stats.medianDaysFirstProposalToSigning && (
              <Reveal delay={160}>
                <Card className="p-5">
                  <InsightBar
                    value={stats.medianDaysFirstProposalToSigning.value}
                    domain={[0, 365]}
                    valueLabel={`~${(stats.medianDaysFirstProposalToSigning.value / 30.44).toFixed(1)} months`}
                    domainLabels={["0 mo", "12 mo"]}
                  />
                  <p className="mt-3 text-sm text-ink-muted">
                    From the first priced proposal to a signed agreement takes a median of{" "}
                    {Math.round(stats.medianDaysFirstProposalToSigning.value)} days (n ={" "}
                    {stats.medianDaysFirstProposalToSigning.n}) — a quarter of a year once real numbers are on the
                    table.
                  </p>
                </Card>
              </Reveal>
            )}
          </div>
        </Container>
      </section>

      {/* How it works */}
      <section className="py-20">
        <Container wide>
          <Reveal>
            <SectionHeading
              eyebrow="Methodology"
              title="From filing to sourced timeline"
              description="Four steps, each one checked against the last, so every number on this site traces back to a real sentence in a real filing."
            />
          </Reveal>
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((step, i) => (
              <div key={step.title} className="relative rounded-lg border border-border bg-surface p-5">
                <span className="font-serif text-3xl text-accent">{String(i + 1).padStart(2, "0")}</span>
                <h3 className="mt-3 text-base font-semibold text-ink">{step.title}</h3>
                <p className="mt-2 text-sm text-ink-muted">{step.body}</p>
              </div>
            ))}
          </div>
          <p className="mt-6 inline-block rounded-lg bg-bg/90 px-4 py-2 text-sm text-ink-muted backdrop-blur-sm">
            <Link href="/methodology" className="text-accent hover:underline">
              Read the full methodology →
            </Link>
          </p>
        </Container>
      </section>

      {/* Featured deals -- the one place besides the hero where imagery
          shows up on this page, per the site's "near-black, imagery at
          most once more below the hero" direction. A single static
          frame, heavily darkened, not the hero's animated loop. */}
      {featured.length > 0 && (
        <section className="relative overflow-hidden border-t border-border py-20">
          <div className="absolute inset-0 -z-10">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/img/hero-photo-6.jpg" alt="" aria-hidden className="h-full w-full object-cover opacity-[0.12]" />
            <div className="absolute inset-0 bg-bg/70" />
          </div>
          <Container wide>
            <Reveal>
              <SectionHeading eyebrow="Coverage" title="Featured deals" />
            </Reveal>
            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {featured.map((deal) => (
                <FeaturedDealCard key={deal.slug} deal={deal} />
              ))}
            </div>
            <p className="mt-6 inline-block rounded-lg bg-bg/90 px-4 py-2 text-sm text-ink-muted backdrop-blur-sm">
              <Link href="/deals" className="text-accent hover:underline">
                Browse all {headlineCount} deals →
              </Link>
            </p>
          </Container>
        </section>
      )}

      {/* Credibility */}
      <section className="border-t border-border py-20">
        <Container wide>
          <Reveal>
            <SectionHeading
              eyebrow="Accuracy"
              title="Checked against gold-standard answer keys"
              description="Before any deal is trusted, its extraction is scored against a hand-checked set of events and proposals read directly off the filing."
            />
          </Reveal>
          <div className="mt-10 grid gap-5 sm:grid-cols-3">
            <Reveal>
              <Card className="p-5">
                <p className="text-sm font-medium text-ink">Splunk &mdash; Cisco (development set)</p>
                <p className="mt-1 text-2xl font-serif text-accent">100%</p>
                <p className="mt-1 text-sm text-ink-muted">core events and proposals match the gold answer key</p>
              </Card>
            </Reveal>
            <Reveal delay={80}>
              <Card className="p-5">
                <p className="text-sm font-medium text-ink">Zendesk &mdash; Consortium (held-out)</p>
                <p className="mt-1 text-2xl font-serif text-accent">97% / 100%</p>
                <p className="mt-1 text-sm text-ink-muted">core-event recall / proposal recall, never seen during development</p>
              </Card>
            </Reveal>
            <Reveal delay={160}>
              <Card className="p-5">
                <p className="text-sm font-medium text-ink">Round-3 spot check (bulk sample)</p>
                <p className="mt-1 text-2xl font-serif text-accent">81 / 90</p>
                <p className="mt-1 text-sm text-ink-muted">fields correct on a fresh random sample of 20 deals</p>
              </Card>
            </Reveal>
          </div>
          <p className="mt-6 inline-block rounded-lg bg-bg/90 px-4 py-2 text-sm text-ink-muted backdrop-blur-sm">
            <Link href="/methodology" className="text-accent hover:underline">
              See the full accuracy methodology →
            </Link>
          </p>
        </Container>
      </section>
    </div>
  );
}
