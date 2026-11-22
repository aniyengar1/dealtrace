import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Every page here reads live from Postgres (deal lists, review state) --
  // deliberately not opting into cacheComponents/PPR, which would require
  // explicit "use cache" annotations to avoid stale/static reads.
  turbopack: {
    rules: {
      // Restrict the Tailwind entry loader to global CSS. Its `as` rewrite
      // strips CSS-module identity when applied to *.module.css. Next handles
      // module scoping and class exports natively.
      "globals.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
