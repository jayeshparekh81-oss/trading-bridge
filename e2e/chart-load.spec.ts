/**
 * Chart page flow.
 *
 * Asserts the chart route loads without console errors. The chart
 * page has complex WebSocket + lightweight-charts integration that's
 * historically been a source of runtime crashes.
 */

import { expect, mockBackend, setupFakeAuth, test } from "./fixtures";

test.describe("Chart load", () => {
  test("/chart loads without console errors", async ({
    page,
    consoleErrors,
  }) => {
    await setupFakeAuth(page);
    await mockBackend(page);

    // Mock chart history endpoint
    await page.route("**/api/chart/history*", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          symbol: "NIFTY",
          timeframe: "5m",
          candles: [
            {
              timestamp: new Date(Date.now() - 5 * 60_000).toISOString(),
              open: 22000,
              high: 22050,
              low: 21980,
              close: 22020,
              volume: 1000,
            },
            {
              timestamp: new Date().toISOString(),
              open: 22020,
              high: 22070,
              low: 22010,
              close: 22050,
              volume: 1200,
            },
          ],
        }),
      });
    });

    await page.goto("/chart");
    await page.waitForLoadState("networkidle");

    // Critical-flow assertion: no console errors. WebSocket may fail
    // to connect (no backend running for ws in E2E test); that's
    // logged but classified separately so we filter ws errors out
    // for the no-crash assertion.
    const fatalErrors = consoleErrors.filter(
      (e) => !/websocket|ws:/i.test(e),
    );
    expect(fatalErrors).toEqual([]);
  });
});
