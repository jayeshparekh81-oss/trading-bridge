/**
 * Login flow smoke test.
 *
 * Visits /login, asserts the form renders, asserts no console errors.
 * NOT testing actual auth (we don't have test credentials).
 */

import { expect, test } from "./fixtures";

test.describe("Login flow", () => {
  test("login page renders without console errors", async ({
    page,
    consoleErrors,
  }) => {
    await page.goto("/login");
    // Some form element exists (input or button labeled appropriately)
    const formExists = await page
      .locator("form")
      .first()
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    const hasLoginText = await page
      .getByText(/login|sign in|email/i)
      .first()
      .isVisible({ timeout: 5_000 })
      .catch(() => false);
    expect(formExists || hasLoginText).toBe(true);
    // No console errors during initial load
    expect(consoleErrors).toEqual([]);
  });
});
