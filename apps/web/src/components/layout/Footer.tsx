import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="space-y-1.5">
          <p>
            Source: <span className="text-ink">SEC EDGAR</span> merger-proxy and tender-offer filings (DEFM14A,
            SC 14D9, S-4). Coverage: deals announced 2021 onward; see{" "}
            <Link href="/methodology" className="text-accent hover:underline">
              Methodology
            </Link>{" "}
            for exclusions.
          </p>
          <p>Research project; not investment advice.</p>
          <p className="text-ink-faint">
            Hero imagery:{" "}
            <a href="https://unsplash.com/@flyshoot" className="hover:text-accent" target="_blank" rel="noreferrer">
              Ryan Fleischer
            </a>
            ,{" "}
            <a href="https://unsplash.com/@jorgenchu" className="hover:text-accent" target="_blank" rel="noreferrer">
              Jorge Garcia
            </a>
            , Dominik Hofbauer,{" "}
            <a href="https://unsplash.com/@andersjilden" className="hover:text-accent" target="_blank" rel="noreferrer">
              Anders Jildén
            </a>
            , Benjamin Child,{" "}
            <a href="https://unsplash.com/@bennieray" className="hover:text-accent" target="_blank" rel="noreferrer">
              Bennie Bates
            </a>
            ,{" "}
            <a href="https://unsplash.com/@davidvives" className="hover:text-accent" target="_blank" rel="noreferrer">
              David Vives
            </a>
            ,{" "}
            <a href="https://unsplash.com/@redtulipsky" className="hover:text-accent" target="_blank" rel="noreferrer">
              Amelia
            </a>{" "}
            (Unsplash) &amp; video via{" "}
            <a href="https://mixkit.co" className="hover:text-accent" target="_blank" rel="noreferrer">
              Mixkit
            </a>
            . Full{" "}
            <a href="/CREDITS.md" className="hover:text-accent" target="_blank" rel="noreferrer">
              credits
            </a>
            .
          </p>
        </div>
        <div className="flex items-center gap-4 text-ink-muted">
          <span>
            Built by{" "}
            <a href="https://github.com/aniyengar1" className="text-ink hover:text-accent" target="_blank" rel="noreferrer">
              Anirudh Iyengar
            </a>
          </span>
          <a href="https://github.com/aniyengar1" className="hover:text-accent" target="_blank" rel="noreferrer">
            GitHub
          </a>
          <a
            href="https://www.linkedin.com/in/anirudh-iyengar-0a5627282"
            className="hover:text-accent"
            target="_blank"
            rel="noreferrer"
          >
            LinkedIn
          </a>
        </div>
      </div>
    </footer>
  );
}
