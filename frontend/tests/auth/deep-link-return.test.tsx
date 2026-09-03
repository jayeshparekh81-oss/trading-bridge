/**
 * A shared deep link returns the customer to where they were going.
 *
 * Found in the production walkthrough: every dashboard route redirected to a
 * bare /login, dropping the destination. A customer clicking a shared
 * /marketplace/<id> link logged in and landed on the homepage with no way back
 * to the thing they clicked.
 *
 * The machinery already existed — withNext/safeNextPath, built for the
 * Subscribe CTA. The general auth guard simply was not using it. That also
 * means the open-redirect protection comes along for free: the path is
 * sanitised before it can become a post-login navigation.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { withNext, safeNextPath, DEFAULT_NEXT } from "@/lib/safe-next";

const LAYOUT = readFileSync(
  join(process.cwd(), "src/app/(dashboard)/layout.tsx"), "utf8");

describe("the dashboard auth guard preserves the destination", () => {
  it("no longer pushes a bare /login", () => {
    expect(LAYOUT).not.toMatch(/router\.push\("\/login"\)/);
  });

  it("uses the SAME sanitiser as the Subscribe CTA", () => {
    expect(LAYOUT).toContain('withNext("/login"');
    expect(LAYOUT).toContain('from "@/lib/safe-next"');
  });

  it("builds the target from the current location", () => {
    expect(LAYOUT).toMatch(/window\.location\.pathname \+ window\.location\.search/);
  });
});

describe("the destination it produces", () => {
  it.each([
    ["/marketplace/931d38f4-406e-46ec-88f9-5212b21a4d3b"],
    ["/strategies/abc"],
    ["/marketplace/me?sub=1"],
  ])("round-trips %s", (path) => {
    const url = withNext("/login", path);
    expect(url).toBe(`/login?next=${encodeURIComponent(path)}`);
    expect(safeNextPath(new URLSearchParams(url.split("?")[1]).get("next"))).toBe(path);
  });

  it("🔴 an off-site location can never become the destination", () => {
    // The guard reads window.location, so this is defence in depth rather than
    // the primary threat — but the sanitiser is what makes it safe to feed a
    // location into a post-login redirect at all.
    expect(withNext("/login", "https://evil.example")).toBe("/login");
    expect(withNext("/login", "//evil.example")).toBe("/login");
    expect(safeNextPath("https://evil.example")).toBe(DEFAULT_NEXT);
  });

  it("omits ?next when the destination is just the homepage", () => {
    expect(withNext("/login", "/")).toBe("/login");
  });
});
