import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import { NavBar } from "@/components/layout/NavBar";
import { Footer } from "@/components/layout/Footer";
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

const siteUrl = "https://dealtrace.example";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "DealTrace — Every public-company sale process, sourced from SEC filings",
    template: "%s · DealTrace",
  },
  description:
    "DealTrace extracts how public-company M&A sale processes actually unfold -- who was contacted, how bids moved, how long it took -- from SEC merger-proxy filings, with every fact linked to its source quote.",
  openGraph: {
    title: "DealTrace",
    description:
      "Every public-company sale process since 2021, extracted from SEC filings and linked to its source.",
    url: siteUrl,
    siteName: "DealTrace",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "DealTrace",
    description: "Every public-company sale process since 2021, extracted from SEC filings.",
  },
};

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
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
