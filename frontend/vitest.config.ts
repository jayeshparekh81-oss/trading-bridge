import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: [
        "src/lib/chart/**",
        "src/hooks/useChartWebSocket.ts",
        "src/hooks/useChartHistory.ts",
        "src/hooks/useWsToken.ts",
        "src/components/chart/**",
      ],
      // R5 coverage tiers documented in PATCH_INSTRUCTIONS_FRONTEND.md.
      // No inline thresholds yet — Day-5 ships with the WS hook's
      // deep-lifecycle tests deferred to Day 4 (jsdom + fake-WebSocket
      // combination drives an unbounded reconnect loop under
      // ``vitest --pool=forks``). Operator enables per-module
      // thresholds once the Day-4 msw-based ws-mock tests land.
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(dirname, "./src"),
    },
  },
});
