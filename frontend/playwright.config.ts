/**
 * Playwright config — chart-module E2E smoke tests.
 *
 * Phase 6 scope:
 *   * Mock-mode only — every fetch routes through the
 *     ``NEXT_PUBLIC_USE_MOCK=true`` path so the suite has no
 *     dependency on a live backend or paper-trading data.
 *   * Chromium only. Multi-browser comes after launch.
 *   * Run against a dev server the operator boots manually OR
 *     the ``webServer`` block below auto-starts ``next dev`` on
 *     port 3100 to avoid clashing with the operator's own
 *     localhost:3000 dev session.
 *
 * Run:
 *     npm run test:e2e               # headless, single project
 *     npm run test:e2e -- --headed   # see the browser
 *     npm run test:e2e -- --ui       # Playwright UI mode
 */

import { defineConfig, devices } from "@playwright/test";

const E2E_PORT = Number(process.env.E2E_PORT ?? 3100);
const BASE_URL = process.env.E2E_BASE_URL ?? `http://localhost:${E2E_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  // 30s per test is generous for the chart's mount + canvas
  // first-paint cycle — the WS hook + history fetch resolve in
  // mock mode within ~50ms but the canvas itself takes a beat.
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  // CI gets one retry to absorb the occasional flaky canvas
  // first-paint; locally the suite must pass first try so the
  // operator notices regressions immediately.
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI
    ? [["github"], ["list"]]
    : [["list"]],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } },
    },
  ],
  // Auto-start ``next dev`` on E2E_PORT for local runs. Skip when
  // E2E_BASE_URL is set externally (CI / operator pointing at a
  // pre-warmed server). Reuses an existing server if one is
  // already running on the port.
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        // Use the locally-installed Next via ``npm exec`` so the
        // command runs without requiring a global ``next`` binary
        // on PATH (CI runners + minimal-PATH shells both work).
        command: `npm exec --silent -- next dev -p ${E2E_PORT}`,
        port: E2E_PORT,
        reuseExistingServer: true,
        timeout: 60_000,
        env: { NEXT_PUBLIC_USE_MOCK: "true" },
      },
});
