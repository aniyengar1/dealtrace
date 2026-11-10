import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Every page here reads live from Postgres (deal lists, review state) --
  // deliberately not opting into cacheComponents/PPR, which would require
  // explicit "use cache" annotations to avoid stale/static reads.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
