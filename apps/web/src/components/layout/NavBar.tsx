import Link from "next/link";
import { SearchBox } from "./SearchBox";

const LINKS = [
  { href: "/deals", label: "Deals" },
  { href: "/methodology", label: "Methodology" },
  { href: "/stats", label: "Stats" },
  { href: "/crosscheck/predictions", label: "Crosscheck" },
];

export function NavBar() {
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/85 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3 sm:px-6">
        <Link href="/" className="font-serif text-lg font-semibold tracking-tight text-ink">
          DealTrace
        </Link>
        <div className="hidden items-center gap-5 sm:flex">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-ink-muted transition-colors hover:text-ink"
            >
              {link.label}
            </Link>
          ))}
        </div>
        <Link href="/crosscheck/predictions" className="text-sm text-ink-muted sm:hidden">Crosscheck</Link>
        <div className="ml-auto w-full max-w-[220px]">
          <SearchBox />
        </div>
      </nav>
    </header>
  );
}
