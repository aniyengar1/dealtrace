import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import { NavBar } from "@/components/layout/NavBar";
import { Footer } from "@/components/layout/Footer";
import { PageTransition } from "@/components/layout/PageTransition";
import { getIncludedDealsSummary } from "@/lib/homeStats";
import { SITE_URL } from "@/lib/site";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  axes: ["opsz", "SOFT", "WONK"],
  display: "swap",
});

const siteUrl = SITE_URL;

// Dynamic rather than a static `metadata` export so the headline count
// in <title> and the meta description always matches the real
// canonical deal count instead of a claim that drifts out of date
// (or a blanket "every" that promises more coverage than exists).
export async function generateMetadata(): Promise<Metadata> {
  const { count: n, minSigningYear } = await getIncludedDealsSummary();
  const since = minSigningYear ?? 2021;
  const description = `DealTrace has extracted ${n} public-company sale processes from SEC filings since ${since} -- who was contacted, how bids moved, how long it took -- with every fact linked to its source quote.`;
  return {
    metadataBase: new URL(siteUrl),
    title: {
      default: `DealTrace — ${n} public-company sale processes, sourced from SEC filings`,
      template: "%s · DealTrace",
    },
    description,
    openGraph: {
      title: "DealTrace",
      description,
      url: siteUrl,
      siteName: "DealTrace",
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: "DealTrace",
      description,
    },
  };
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`h-full antialiased ${inter.variable} ${fraunces.variable}`}>
      <body className="flex min-h-full flex-col bg-bg text-ink">
        <a
          href="#main"
          className="absolute left-2 top-2 -translate-y-16 rounded-md bg-surface-raised px-3 py-2 text-sm text-ink focus-visible:translate-y-0"
        >
          Skip to content
        </a>
        <NavBar />
        <main id="main" className="flex-1">
          <PageTransition>{children}</PageTransition>
        </main>
        <Footer />
      </body>
    </html>
  );
}
