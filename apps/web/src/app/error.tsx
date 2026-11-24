"use client";

import { Container } from "@/components/ui/Container";
import { Button } from "@/components/ui/Button";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <Container wide className="py-24 text-center">
      <p className="font-serif text-2xl text-ink">Something went wrong loading this page.</p>
      <p className="mt-2 text-sm text-ink-muted">
        This is usually temporary: the underlying data may still be loading. Try again in a moment.
      </p>
      <Button variant="secondary" className="mt-6" onClick={reset}>
        Try again
      </Button>
    </Container>
  );
}
