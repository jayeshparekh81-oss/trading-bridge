/**
 * Playwright config — e2e test runner for TRADETRI frontend.
 *
 * Tests live at repo root in ./e2e/. Each .spec.ts file targets one
 * critical user flow. Tests run against a LOCAL frontend dev server
 * (Next.js on localhost:3000) — never prod.
 *
 * Setup:
 *   pnpm --filter frontend dev     # start frontend in one terminal
 *   pnpm exec playwright test      # run e2e in another
 *
 * In CI the `webServer` config auto-starts the frontend before tests.
 */

import { defineConfig, devices } from "@playwright/test";

const FRONTEND_BASE = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  timeout: 30_000,
  fullyParallel: false, // sequential to avoid auth-cookie collisions
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",

  use: {
    baseURL: FRONTEND_BASE,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    // Tests run against jsdom-like state; no real auth credentials.
    extraHTTPHeaders: {
      Accept: "application/json, text/html",
    },
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  // CI: auto-start the frontend before tests. Local: skip (developer
  // owns the dev-server). Detect via process.env.CI flag.
  webServer: process.env.CI
    ? {
        command: "cd frontend && npm run dev",
        url: FRONTEND_BASE,
        timeout: 60_000,
        reuseExistingServer: false,
      }
    : undefined,
});
