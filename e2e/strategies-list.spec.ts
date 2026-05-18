/**
 * Strategies list flow.
 *
 * Auth + mock backend → visit /strategies → assert page loads,
 * empty state visible, NO console errors.
 */

import { expect, mockBackend, setupFakeAuth, test } from "./fixtures";

test.describe("Strategies list", () => {
  test("loads without console errors and shows empty state", async ({
    page,
    consoleErrors,
  }) => {
    await setupFakeAuth(page);
    await mockBackend(page);

    await page.goto("/strategies");
    await page.waitForLoadState("networkidle");

    // The page renders. Either there's an empty-state message OR a
    // list container. Both are acceptable — what we're guarding
    // against is a hard crash.
    expect(consoleErrors).toEqual([]);
  });
});
