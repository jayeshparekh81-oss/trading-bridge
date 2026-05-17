/**
 * Template clone flow.
 *
 * Mocks the clone POST → mocks the resulting strategy detail GET →
 * asserts the "Cloned from template" badge renders + no console errors.
 *
 * This is the flow that would catch the May-17 P0 (clone detail page
 * showing the wrong "legacy" warning) if it regressed.
 */

import { expect, mockBackend, setupFakeAuth, test } from "./fixtures";

test.describe("Template clone flow", () => {
  test("clone POST → detail page shows Cloned from template badge", async ({
    page,
    consoleErrors,
  }) => {
    await setupFakeAuth(page);
    await mockBackend(page);

    const newStrategyId = "11111111-2222-3333-4444-555555555555";

    // Mock the clone POST
    await page.route(
      "**/api/templates/test-template/clone",
      async (route) => {
        if (route.request().method() !== "POST") {
          await route.continue();
          return;
        }
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            strategy_id: newStrategyId,
            strategy_name: "Test Template (from template)",
            template_slug: "test-template",
            message: "Strategy cloned",
          }),
        });
      },
    );

    // Mock the strategy detail GET with template_origin populated
    await page.route(
      `**/api/strategies/${newStrategyId}`,
      async (route) => {
        if (route.request().method() !== "GET") {
          await route.continue();
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: newStrategyId,
            name: "Test Template (from template)",
            is_active: true,
            strategy_json: null,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            current_version_number: null,
            template_origin: {
              template_slug: "test-template",
              template_name: "Test Template",
              template_category: "Trend Following",
              template_complexity: "beginner",
              cloned_at: new Date().toISOString(),
              config_json: {
                indicators: ["ema"],
                stop_loss_pct: 1.0,
                take_profit_pct: 2.0,
                trading_hours: { start: "09:15", end: "15:15" },
              },
            },
          }),
        });
      },
    );

    // Navigate directly to the detail page (skipping the actual click
    // to keep test fast — what matters is the detail page render).
    await page.goto(`/strategies/${newStrategyId}`);
    await page.waitForLoadState("networkidle");

    // The "Cloned from template" badge MUST render
    const badge = page.getByText(/Cloned from template/i).first();
    await expect(badge).toBeVisible({ timeout: 5_000 });

    // Pre-Phase-5 legacy warning MUST NOT render
    const legacy = page.getByText(/Phase 5 builder se pehle bani thi/i);
    await expect(legacy).not.toBeVisible();

    // No console errors during render
    expect(consoleErrors).toEqual([]);
  });
});
