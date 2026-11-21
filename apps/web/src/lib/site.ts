// Set in production (Vercel project env vars); falls back to the local
// dev server's own origin so sitemap/metadata URLs are still correct
// when running `next dev` without SITE_URL configured.
export const SITE_URL = process.env.SITE_URL || "http://localhost:3000";
