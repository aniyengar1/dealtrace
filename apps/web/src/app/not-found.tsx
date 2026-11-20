import { Container } from "@/components/ui/Container";
import { LinkButton } from "@/components/ui/Button";

// Reached when notFound() is called from inside a page component --
// proxy.ts is the one that actually intercepts most bad /deals/:slug
// requests before they get this far (see its own comment on why), so
// this is the fallback for everything else: a genuinely unknown route,
// or a defense-in-depth catch if a page's own check fires first.
export default function NotFound() {
  return (
    <Container className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink">Deal not found</h1>
      <p className="mt-2 max-w-sm text-sm text-ink-muted">
        This deal doesn&apos;t exist, or isn&apos;t part of DealTrace&apos;s public dataset.
      </p>
      <LinkButton href="/deals" variant="primary" className="mt-6">
        ← Back to deals
      </LinkButton>
    </Container>
  );
}
