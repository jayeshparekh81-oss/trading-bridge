/**
 * Playwright config — production launch-smoke suite.
 *
 * Read-only run against https://tradetri.com + https://api.tradetri.com
 * (overridable via E2E_SMOKE_BASE_URL / E2E_SMOKE_API_BASE_URL).
 * Distinct from the default `playwright.config.ts`, which auto-starts
 * a local Next dev server in mock mode for the chart suite.
 *
 * Run:
 *     npx playwright test -c playwright.smoke.config.ts
 *
 * Screenshots land in `tests/e2e/screenshots/`; HTML reports in
 * `playwright-report-smoke/`. Both are git-ignored.
 */

import { defineConfig, devices } from "@playwright/test";

const BASE_URL =
  process.env.E2E_SMOKE_BASE_URL ?? "https://tradetri.com";
const API_BASE_URL =
  process.env.E2E_SMOKE_API_BASE_URL ?? "https://api.tradetri.com";

export default defineConfig({
  testDir: "./e2e",
  testMatch: /launch-smoke\.spec\.ts$/,
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI
    ? [["github"], ["list"], ["html", { open: "never", outputFolder: "playwright-report-smoke" }]]
    : [["list"], ["html", { open: "never", outputFolder: "playwright-report-smoke" }]],
  outputDir: "./playwright-results-smoke",
  use: {
    baseURL: BASE_URL,
    extraHTTPHeaders: {
      "x-e2e-api-base": API_BASE_URL,
    },
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    ignoreHTTPSErrors: false,
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
      },
    },
  ],
});
