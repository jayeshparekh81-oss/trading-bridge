import type { NextConfig } from "next";

/**
 * Next config with Phase-1 perf wins enabled. Production-data-driven
 * tuning (cache headers per route, preconnect hints, edge runtime
 * opt-ins) lands in Phase 2 once we have real RUM numbers.
 */
const nextConfig: NextConfig = {
  // Server-side gzip on static + SSR responses. Cheap; saves
  // ~70% on JSON / HTML transfer sizes.
  compress: true,

  // Source maps in the production bundle 3-4x the JS payload
  // shipped to clients. We keep them off by default; flip via
  // NEXT_PUBLIC_DEBUG_BUILD=1 when actively investigating a
  // production-only bug.
  productionBrowserSourceMaps: process.env.NEXT_PUBLIC_DEBUG_BUILD === "1",

  // Strip the "X-Powered-By: Next.js" leak.
  poweredByHeader: false,

  // React strict mode — the existing baseline relies on it; making
  // it explicit so a future config rewrite doesn't quietly drop it.
  reactStrictMode: true,

  // Image pipeline. Modern formats first, fall back to PNG/JPEG.
  // Remote patterns intentionally empty until we wire a CDN
  // (Phase 2). Allowing arbitrary remote hosts here would let any
  // third-party page abuse our /_next/image proxy as a free CDN.
  images: {
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 60,
    remotePatterns: [],
  },

  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://43.205.195.227:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
