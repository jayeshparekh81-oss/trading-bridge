/**
 * Chart-route E2E smoke — overnight #2 / Phase 6.
 *
 * Mock-mode only. Auth is bypassed by:
 *   1. Seeding localStorage with a placeholder access token before
 *      the chart route navigates (so AuthProvider's mount effect
 *      doesn't redirect to /login).
 *   2. Intercepting GET /api/auth/me via page.route() — returns a
 *      synthetic User payload that satisfies the dashboard layout's
 *      onboarding-step >= 6 check.
 *
 * Real-backend integration lands tomorrow after the smoke test
 * goes green; Phase-6 only proves the wiring + the smoke surface
 * area is exercisable.
 */

import { expect, test } from "@playwright/test";

// ─── Shared setup ─────────────────────────────────────────────────────

const FAKE_USER = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "smoke@tradetri.test",
  full_name: "Smoke Tester",
  phone: null,
  is_active: true,
  is_admin: false,
  role: "user",
  telegram_chat_id: null,
  notification_prefs: {},
  created_at: "2026-01-01T00:00:00+00:00",
  onboarding_step: 6,
  onboarding_completed_at: "2026-01-01T00:00:00+00:00",
};

test.beforeEach(async ({ context, page }) => {
  // 1. Seed tokens into localStorage BEFORE the page mounts.
  await context.addInitScript(() => {
    window.localStorage.setItem("tb_access_token", "e2e-test-token");
    window.localStorage.setItem("tb_refresh_token", "e2e-test-refresh");
  });

  // 2. Intercept /api/auth/me so AuthProvider's fetchUser succeeds.
  //    Every other /api/* call is left untouched — the chart route
  //    runs in NEXT_PUBLIC_USE_MOCK=true mode (set in the
  //    playwright webServer block) so the chart hooks short-circuit
  //    to in-memory fixtures without hitting the backend at all.
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(FAKE_USER),
    }),
  );
});

// ─── Smoke tests ──────────────────────────────────────────────────────

test("chart route loads and renders the canvas + top bar", async ({ page }) => {
  await page.goto("/chart");
  await expect(page.getByTestId("chart-container")).toBeVisible();
  await expect(page.getByTestId("chart-top-bar")).toBeVisible();
  await expect(page.getByTestId("candlestick-chart-container")).toBeVisible({
    timeout: 10_000,
  });
});

test("symbol switch updates the input value", async ({ page }) => {
  await page.goto("/chart");
  await expect(page.getByTestId("symbol-input")).toHaveValue("NIFTY");
  // Quick-pick chip — visible at sm+; we're on desktop viewport.
  await page.getByTestId("symbol-quick-BANKNIFTY").click();
  await expect(page.getByTestId("symbol-input")).toHaveValue("BANKNIFTY");
});

test("timeframe switch sets the active button", async ({ page }) => {
  await page.goto("/chart");
  await page.getByTestId("timeframe-15m").click();
  await expect(page.getByTestId("timeframe-15m")).toHaveAttribute(
    "aria-checked",
    "true",
  );
  await expect(page.getByTestId("timeframe-5m")).toHaveAttribute(
    "aria-checked",
    "false",
  );
});

test("status pill flips to live after the WS opens (mock mode)", async ({
  page,
}) => {
  await page.goto("/chart");
  // Mock WS server starts emitting after the token resolves; the
  // pill's data-state attribute is the canonical surface.
  await expect(page.getByTestId("chart-status-pill")).toHaveAttribute(
    "data-state",
    "live",
    { timeout: 10_000 },
  );
});

test("strategy selector loads + populates with mock strategies", async ({
  page,
}) => {
  await page.goto("/chart");
  const select = page.getByTestId("strategy-select");
  await expect(select).toBeVisible();
  // Mock fixture ships 3 strategies — the placeholder + 3 should
  // give 4 options.
  await expect(select.locator("option")).toHaveCount(4, { timeout: 5_000 });
});

test("indicators dropdown opens and shows the 5 toggles", async ({ page }) => {
  await page.goto("/chart");
  await page.getByTestId("indicators-dropdown-toggle").click();
  await expect(
    page.getByTestId("indicators-dropdown-menu"),
  ).toBeVisible();
  await expect(page.getByTestId("indicator-toggle-sma20")).toBeVisible();
  await expect(page.getByTestId("indicator-toggle-ema50")).toBeVisible();
  await expect(page.getByTestId("indicator-toggle-rsi")).toBeVisible();
  await expect(page.getByTestId("indicator-toggle-macd")).toBeVisible();
  await expect(page.getByTestId("indicator-toggle-volume")).toBeVisible();
});

test("paper trade list renders the 'select a strategy' empty state", async ({
  page,
}) => {
  await page.goto("/chart");
  // Default state — no strategy auto-selected on first visit.
  await expect(page.getByTestId("paper-trade-list-empty")).toContainText(
    /strategy select karo/i,
  );
});

test("header info row renders the symbol + price after candles load", async ({
  page,
}) => {
  await page.goto("/chart");
  // Wait for the loaded state (candles arrived from mock).
  await expect(page.getByTestId("chart-header-info")).toHaveAttribute(
    "data-state",
    "loaded",
    { timeout: 10_000 },
  );
  await expect(page.getByTestId("header-price")).toContainText(/₹/);
});
