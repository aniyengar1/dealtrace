// Pure constants/types shared by the server-only deal metrics query
// logic (dealMetrics.ts) and client components (FilterBar) that render
// filter controls -- kept out of dealMetrics.ts itself so importing
// them never pulls the "server-only" / pg-backed module into a client
// bundle.

export type PriceBucket = "under-20" | "20-50" | "50-100" | "over-100" | "unknown";

export const PRICE_BUCKET_LABELS: Record<PriceBucket, string> = {
  "under-20": "Under $20",
  "20-50": "$20 – $50",
  "50-100": "$50 – $100",
  "over-100": "$100+",
  unknown: "Unknown",
};

export const CONSIDERATION_TYPE_LABELS: Record<string, string> = {
  cash: "Cash",
  stock: "Stock",
  mixed: "Cash + stock",
  unknown: "Unknown",
};

export type SortKey = "signingDate" | "finalPrice" | "nBidders" | "nProposals" | "pctChange";
export type SortDir = "asc" | "desc";
