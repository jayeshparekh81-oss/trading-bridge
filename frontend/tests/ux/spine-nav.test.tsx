/**
 * STEP 1 — the journey's spine must be REACHABLE.
 *
 * The audit's findings #3 and #4: /marketplace/me was missing from the sidebar,
 * and Marketplace was absent from mobile navigation ENTIRELY — so on a phone the
 * whole subscribe journey could not be reached by clicking.
 *
 * These read the nav source directly, because the defect was never a rendering
 * bug — the entries simply did not exist.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const read = (p: string) => readFileSync(join(process.cwd(), p), "utf8");
const SIDEBAR = read("src/components/dashboard/sidebar.tsx");
const DRAWER = read("src/components/dashboard/mobile-drawer.tsx");
const BOTTOM = read("src/components/dashboard/mobile-nav.tsx");

describe("sidebar (desktop)", () => {
  it("links Marketplace", () => {
    expect(SIDEBAR).toContain('href: "/marketplace"');
  });
  it("links My Strategies — finding #3", () => {
    expect(SIDEBAR).toContain('href: "/marketplace/me"');
    expect(SIDEBAR).toContain('label: "My Strategies"');
  });
});

describe("mobile drawer — finding #4", () => {
  it("links Marketplace (was entirely absent)", () => {
    expect(DRAWER).toContain('href: "/marketplace"');
  });
  it("links My Strategies (was entirely absent)", () => {
    expect(DRAWER).toContain('href: "/marketplace/me"');
  });
});

describe("mobile bottom bar — finding #4", () => {
  it("reaches the subscribe journey", () => {
    expect(BOTTOM).toContain("/marketplace/me");
  });
  it("still fits 5 slots", () => {
    const count = (BOTTOM.match(/href: "/g) || []).length;
    expect(count).toBeLessThanOrEqual(5);
  });
});

describe("vocabulary — Tradetron/StrykeX words", () => {
  it('no surface still says "My Marketplace"', () => {
    for (const src of [SIDEBAR, DRAWER, BOTTOM, read("src/app/(dashboard)/marketplace/me/page.tsx")]) {
      expect(src).not.toContain("My Marketplace");
    }
  });
  it('the page is titled "My Strategies"', () => {
    expect(read("src/app/(dashboard)/marketplace/me/page.tsx")).toContain("My Strategies");
  });
});
