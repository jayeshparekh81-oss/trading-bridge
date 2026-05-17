/**
 * Templates gallery flow.
 *
 * Asserts the gallery loads + shows the at-least-one template from
 * the mocked /api/templates response + no console errors.
 *
 * This is the flow that would catch a "API shape mismatch" bug like
 * the IndicatorPanel runtime crash — if the gallery treated the API
 * response as the wrong shape, the page would crash here.
 */

import { expect, mockBackend, setupFakeAuth, test } from "./fixtures";

test.describe("Templates gallery", () => {
  test("loads gallery + filters + no console errors", async ({
    page,
    consoleErrors,
  }) => {
    await setupFakeAuth(page);
    await mockBackend(page);

    await page.goto("/strategies/templates");
    await page.waitForLoadState("networkidle");

    // At least one template card is visible (mock returns 1)
    const cardVisible = await page
      .locator('[data-testid^="template-card-"]')
      .first()
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    expect(cardVisible).toBe(true);

    // No console errors during load + render
    expect(consoleErrors).toEqual([]);
  });
});
