import Link from "next/link";
import { listDealsSummary } from "@/lib/queries";
import { computeHomeStats } from "@/lib/homeStats";
import { Container } from "@/components/ui/Container";
import { Card } from "@/components/ui/Card";
import { LinkButton } from "@/components/ui/Button";
import { StatNumber } from "@/components/ui/StatNumber";
import { SectionHeading } from "@/components/ui/SectionHeading";
import { Reveal } from "@/components/ui/Reveal";
import { HeroBumpChart } from "./HeroBumpChart";
import { FeaturedDealCard } from "./FeaturedDealCard";
import { HeroMedia } from "./HeroMedia";
import { DealTicker } from "./DealTicker";

export const dynamic = "force-dynamic";

const STEPS = [
  {
    title: "SEC filing",
    body: "A DEFM14A, SC 14D9, or S-4 merger proxy is fetched and cached from EDGAR the moment it's filed.",
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
  const [deals, stats] = await Promise.all([listDealsSummary(), computeHomeStats()]);
  const featured = FEATURED_SLUGS.map((slug) => deals.find((d) => d.slug === slug)).filter(
    (d): d is NonNullable<typeof d> => d !== undefined && d.n_facts_total > 0
  );

  return (
    <div>
      {/* Hero */}
      <section className="relative isolate overflow-hidden border-b border-border">
        <HeroMedia />
        <Container
          wide
          className="relative grid grid-cols-1 gap-10 py-20 sm:py-28 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:py-36"
        >
          <div>
            <h1 className="font-serif text-4xl font-semibold leading-[1.1] tracking-tight text-ink sm:text-5xl lg:text-6xl">
              Every public-company sale process since 2021, extracted from SEC filings.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-ink-muted">
              DealTrace reconstructs how M&amp;A sale processes actually unfold &mdash; who was contacted, how bids
              moved, how long it took &mdash; with every fact linked back to the exact sentence it came from.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <LinkButton href="/deals" variant="primary">
                Explore deals
              </LinkButton>
              <LinkButton href="/methodology" variant="secondary">
                How it works
              </LinkButton>
            </div>
          </div>
          <Card className="p-5">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
              Distribution of first proposal &rarr; final price change
            </p>
            {stats.medianPctBump ? (
              <div className="mt-3">
                <HeroBumpChart data={stats.pctBumpHistogram} />
                <p className="mt-1 text-xs text-ink-faint">n = {stats.medianPctBump.n} deals with a priced first and final proposal</p>
              </div>
            ) : (
              <p className="mt-3 text-sm text-ink-faint">Not enough priced proposals yet to chart.</p>
            )}
          </Card>
        </Container>
        {deals.length > 0 && (
          <div className="relative border-t border-border/60 bg-bg/70 py-3 backdrop-blur-sm">
            <DealTicker deals={deals} />
          </div>
        )}
      </section>

      {/* Stats band */}
      <section className="border-b border-border bg-surface/40">
        <Container wide className="py-12">
          <div className="grid grid-cols-2 gap-8 sm:grid-cols-4">
            <StatNumber value={stats.nDealsCovered} label="Deals covered" size="lg" />
            {stats.medianBidders && (
              <StatNumber
                value={stats.medianBidders.value}
                decimals={1}
                label="Median distinct bidders per deal"
                n={stats.medianBidders.n}
                size="lg"
              />
            )}
            {stats.medianProposals && (
              <StatNumber
                value={stats.medianProposals.value}
                label="Median proposals per deal"
                n={stats.medianProposals.n}
                size="lg"
              />
            )}
            {stats.medianPctBump && (
              <StatNumber
                value={stats.medianPctBump.value}
                prefix={stats.medianPctBump.value >= 0 ? "+" : ""}
                suffix="%"
                label="Median first → final bump"
                n={stats.medianPctBump.n}
                size="lg"
              />
            )}
            {stats.medianDaysToSigning && (
              <StatNumber
                value={stats.medianDaysToSigning.value}
                label="Median days, first contact → signing"
                n={stats.medianDaysToSigning.n}
                size="lg"
              />
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
              <Reveal key={step.title} delay={i * 80}>
                <div className="relative rounded-lg border border-border bg-surface p-5">
                  <span className="font-serif text-3xl text-gold">{String(i + 1).padStart(2, "0")}</span>
                  <h3 className="mt-3 text-base font-semibold text-ink">{step.title}</h3>
                  <p className="mt-2 text-sm text-ink-muted">{step.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
          <p className="mt-6 text-sm text-ink-muted">
            <Link href="/methodology" className="text-gold hover:underline">
              Read the full methodology →
            </Link>
          </p>
        </Container>
      </section>

      {/* Featured deals */}
      {featured.length > 0 && (
        <section className="border-t border-border py-20">
          <Container wide>
            <Reveal>
              <SectionHeading eyebrow="Coverage" title="Featured deals" />
            </Reveal>
            <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {featured.map((deal, i) => (
                <Reveal key={deal.slug} delay={i * 60}>
                  <FeaturedDealCard deal={deal} />
                </Reveal>
              ))}
            </div>
            <p className="mt-6 text-sm text-ink-muted">
              <Link href="/deals" className="text-gold hover:underline">
                Browse all {deals.length} deals →
              </Link>
            </p>
          </Container>
        </section>
      )}

      {/* Credibility */}
      <section className="border-t border-border bg-surface/40 py-20">
        <Container wide>
          <Reveal>
            <SectionHeading
              eyebrow="Accuracy"
              title="Checked against gold-standard answer keys"
              description="Before any deal is trusted, its extraction is scored against a hand-checked set of events and proposals read directly off the filing."
            />
          </Reveal>
          <div className="mt-10 grid gap-5 sm:grid-cols-2">
            <Reveal>
              <Card className="p-5">
                <p className="text-sm font-medium text-ink">Splunk &mdash; Cisco (development set)</p>
                <p className="mt-1 text-2xl font-serif text-gold">100%</p>
                <p className="mt-1 text-sm text-ink-muted">core events and proposals match the gold answer key</p>
              </Card>
            </Reveal>
            <Reveal delay={80}>
              <Card className="p-5">
                <p className="text-sm font-medium text-ink">Zendesk &mdash; Consortium (held-out)</p>
                <p className="mt-1 text-2xl font-serif text-gold">97% / 100%</p>
                <p className="mt-1 text-sm text-ink-muted">recall / precision on core events and proposals, never seen during development</p>
              </Card>
            </Reveal>
          </div>
          <p className="mt-6 text-sm text-ink-muted">
            <Link href="/methodology" className="text-gold hover:underline">
              See the full accuracy methodology →
            </Link>
          </p>
        </Container>
      </section>
    </div>
  );
}
