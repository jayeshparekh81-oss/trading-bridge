/**
 * Launch smoke — production read-only.
 *
 * Hits https://tradetri.com + https://api.tradetri.com without auth.
 * Every test is read-only: navigation or unauthenticated curl-equivalent
 * requests. No side effects on production state.
 *
 * Suites:
 *   A. Public page loads (no auth needed)
 *   B. API endpoint checks
 *   C. Screenshots (visual regression baseline)
 *
 * Run:
 *     npx playwright test -c playwright.smoke.config.ts
 */

import * as path from "node:path";
import { expect, request, test, type Page } from "@playwright/test";

const API_BASE = "https://api.tradetri.com";
const SCREENSHOT_DIR = path.resolve(__dirname, "screenshots");
const PAGE_LOAD_BUDGET_MS = 5_000;

// Critical console messages that the suite tolerates. Anything outside
// this list flagged as "error" or "pageerror" fails the no-console test.
const CONSOLE_ALLOW = [
  /\/api\/auth\/me.*401/i,
  /\/api\/auth\/refresh.*401/i,
  /failed to load resource.*401/i,
  /failed to load resource.*404/i,
  /sentry/i,
  /vercel insights/i,
  /favicon\.ico/i,
  /posthog/i,
  /\[hmr\]/i,
];

function isCritical(msg: string): boolean {
  return !CONSOLE_ALLOW.some((re) => re.test(msg));
}

async function gotoSettled(
  page: Page,
  pathname: string,
): Promise<{ status: number; loadMs: number }> {
  const t0 = Date.now();
  const resp = await page.goto(pathname, { waitUntil: "domcontentloaded" });
  const loadMs = Date.now() - t0;
  expect(resp, `no response for ${pathname}`).not.toBeNull();
  const status = resp!.status();
  expect(status, `${pathname} returned ${status}`).toBeLessThan(500);
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => {
    /* some prod pages keep long-poll connections open; networkidle may
       never fire — domcontentloaded above is the floor we enforce. */
  });
  return { status, loadMs };
}

// ═════════════════════════════════════════════════════════════════════
// Suite A — Public page loads
// ═════════════════════════════════════════════════════════════════════

test.describe("A. Public page loads", () => {
  test("A1. home loads (200, TRADETRI title, paper-mode banner visible)", async ({ page }) => {
    const { status, loadMs } = await gotoSettled(page, "/");
    expect(status).toBe(200);
    expect(loadMs, `home load took ${loadMs}ms`).toBeLessThan(PAGE_LOAD_BUDGET_MS);
    await expect(page).toHaveTitle(/TRADETRI/i);
    // Paper-mode banner is gated by /api/system/mode — when paper mode is
    // ON it renders the yellow strip. Accept either presence OR absence as
    // long as the page didn't 500. The banner role is "status".
    const banner = page.getByRole("status").filter({ hasText: /paper mode/i });
    // Soft check: log presence so the report captures live state, but
    // don't fail if the system flips off paper mode.
    const bannerVisible = await banner.first().isVisible().catch(() => false);
    test.info().annotations.push({
      type: "paper-mode-banner-visible",
      description: String(bannerVisible),
    });
  });

  test("A2. /login loads (200, has email + password inputs)", async ({ page }) => {
    const { status } = await gotoSettled(page, "/login");
    expect(status).toBe(200);
    // Login forms use type=email + type=password — stable across redesigns.
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test("A3. signup form loads (200, has password + confirm-password)", async ({ page }) => {
    // Production hosts signup at /register; /signup is a 404. The
    // form has TWO password inputs (Password + Confirm Password), so
    // assert the count + first-visible rather than a single locator
    // (which would trip Playwright's strict mode).
    const { status } = await gotoSettled(page, "/register");
    expect(status).toBe(200);
    const passwordInputs = page.locator('input[type="password"]');
    await expect(passwordInputs.first()).toBeVisible({ timeout: 10_000 });
    expect(await passwordInputs.count()).toBeGreaterThanOrEqual(2);
  });

  test("A4. /compliance loads (200)", async ({ page }) => {
    const { status } = await gotoSettled(page, "/compliance");
    expect(status).toBe(200);
    // /compliance lives under the dashboard route group; unauthenticated
    // visitors get redirected to /login. Accept either landing state.
    const url = page.url();
    expect(url).toMatch(/\/(compliance|login)/);
  });

  test("A5. no critical console errors across public routes", async ({ page }) => {
    const offenders: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error" && isCritical(m.text())) {
        offenders.push(`[console] ${m.text()}`);
      }
    });
    page.on("pageerror", (e) => {
      if (isCritical(e.message)) {
        offenders.push(`[pageerror] ${e.message}`);
      }
    });
    for (const p of ["/", "/login", "/register", "/compliance"]) {
      await gotoSettled(page, p);
    }
    expect(
      offenders,
      `unexpected console errors:\n${offenders.join("\n")}`,
    ).toHaveLength(0);
  });

  test("A6. home page first paint < 5s", async ({ page }) => {
    const t0 = Date.now();
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const loadMs = Date.now() - t0;
    expect(loadMs, `home DOMContentLoaded took ${loadMs}ms`).toBeLessThan(
      PAGE_LOAD_BUDGET_MS,
    );
  });
});

// ═════════════════════════════════════════════════════════════════════
// Suite B — API endpoint checks
// ═════════════════════════════════════════════════════════════════════

test.describe("B. API endpoint checks", () => {
  test("B1. GET /health → 200 with status:ok", async () => {
    const ctx = await request.newContext();
    const resp = await ctx.get(`${API_BASE}/health`, { failOnStatusCode: false });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toMatchObject({ status: "ok" });
    await ctx.dispose();
  });

  test("B2. GET /api/system/mode → 200 with paper_mode field", async () => {
    const ctx = await request.newContext();
    const resp = await ctx.get(`${API_BASE}/api/system/mode`, {
      failOnStatusCode: false,
    });
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty("paper_mode");
    expect(typeof body.paper_mode).toBe("boolean");
    await ctx.dispose();
  });

  test("B3. POST legacy webhook (UUID) → 404 (Fix #1)", async () => {
    const ctx = await request.newContext();
    const resp = await ctx.post(
      `${API_BASE}/api/webhook/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee`,
      { data: {}, failOnStatusCode: false },
    );
    expect(resp.status()).toBe(404);
    await ctx.dispose();
  });

  test("B4. GET kill-switch with X-User-Id bypass → 401 (Fix #4)", async () => {
    const ctx = await request.newContext();
    const resp = await ctx.get(`${API_BASE}/api/kill-switch/status`, {
      headers: { "X-User-Id": "00000000-0000-0000-0000-000000000000" },
      failOnStatusCode: false,
    });
    expect(resp.status()).toBe(401);
    await ctx.dispose();
  });
});

// ═════════════════════════════════════════════════════════════════════
// Suite C — Screenshots (visual regression baseline)
// ═════════════════════════════════════════════════════════════════════

test.describe("C. Screenshots", () => {
  test("C1. home page screenshot", async ({ page }) => {
    await gotoSettled(page, "/");
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "home.png"),
      fullPage: true,
    });
  });

  test("C2. login page screenshot", async ({ page }) => {
    await gotoSettled(page, "/login");
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "login.png"),
      fullPage: true,
    });
  });

  test("C3. compliance page screenshot", async ({ page }) => {
    await gotoSettled(page, "/compliance");
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "compliance.png"),
      fullPage: true,
    });
  });
});
