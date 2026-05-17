/**
 * Shared Playwright fixtures.
 *
 * Auth fixture: injects a fake JWT into localStorage so the app's
 * useApi/auth hooks think the user is logged in. NO real credentials,
 * NO real backend calls — pages that hit /api/* are caught by the
 * route-mock fixture and served fake JSON.
 *
 * Console-error fixture: every test gets a `consoleErrors` accumulator;
 * any browser console.error fires during the test fails it. This was
 * the explicit gap that let the IndicatorPanel TypeError ship — the
 * crash WAS visible in the browser console but no test was watching.
 */

import { test as base, expect } from "@playwright/test";

export interface E2EFixtures {
  consoleErrors: string[];
}

export const test = base.extend<E2EFixtures>({
  consoleErrors: async ({ page }, use) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        errors.push(msg.text());
      }
    });
    page.on("pageerror", (err) => {
      errors.push(err.message);
    });
    await use(errors);
  },
});

export { expect };

/**
 * Inject a fake auth state so the app's useApi hook + page guards see
 * a "logged-in" user. The fake JWT is signed locally with a dummy
 * payload — the real backend would reject it, but our /api/* calls
 * are mocked.
 */
export async function setupFakeAuth(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    const fakeJwt =
      "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." +
      btoa(
        JSON.stringify({
          sub: "e2e-test-user",
          email: "e2e@tradetri.test",
          exp: Math.floor(Date.now() / 1000) + 3600,
        }),
      ) +
      ".fake-signature";
    localStorage.setItem("access_token", fakeJwt);
    localStorage.setItem("refresh_token", "fake-refresh");
  });
}

/**
 * Mock the backend API surface. Each route returns deterministic
 * fixture data so tests don't depend on a live backend.
 */
export async function mockBackend(page: import("@playwright/test").Page) {
  // GET /api/strategies/indicators — returns the real array shape
  // (the P0 fix was that the frontend treated this as an envelope).
  await page.route("**/api/strategies/indicators", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "ema",
          name: "EMA",
          category: "Trend",
          description: "Exponential MA",
          inputs: [],
          outputs: ["line"],
          chartType: "overlay",
          pineAliases: ["ta.ema"],
          difficulty: "beginner",
          status: "active",
          aiExplanation: "EMA is trend.",
          tags: ["trend"],
          calculationFunction: "ema",
        },
        {
          id: "rsi",
          name: "RSI",
          category: "Momentum",
          description: "Relative Strength",
          inputs: [],
          outputs: ["line"],
          chartType: "separate",
          pineAliases: ["ta.rsi"],
          difficulty: "beginner",
          status: "active",
          aiExplanation: "RSI is momentum.",
          tags: ["momentum"],
          calculationFunction: "rsi",
        },
      ]),
    });
  });

  // GET /api/strategies — returns empty list (newest-first)
  await page.route("**/api/strategies", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ strategies: [], count: 0 }),
    });
  });

  // GET /api/templates — paginated list (frontend reads .items)
  await page.route("**/api/templates*", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "00000000-0000-0000-0000-000000000001",
            slug: "test-template",
            name: "Test Template",
            category: "Trend Following",
            complexity: "beginner",
            description_en: "Test",
            risk_level: "low",
            timeframe: "5m",
            indicators_used: ["ema"],
            tags: ["test"],
            is_active: true,
            requires_options_builder: false,
          },
        ],
        total: 1,
      }),
    });
  });

  // GET /api/users/me — auth check
  await page.route("**/api/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "00000000-0000-0000-0000-000000000099",
        email: "e2e@tradetri.test",
        is_active: true,
        is_admin: false,
      }),
    });
  });
}
