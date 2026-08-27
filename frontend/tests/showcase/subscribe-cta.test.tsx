/**
 * The s1 Subscribe path: the open-redirect guard, the CTA, and the return path.
 *
 * The load-bearing test in this file is the open-redirect one. `?next=` is
 * attacker-supplied and is followed by a browser that has JUST been handed a
 * live session — on a trading platform that is a credential-theft vector, not
 * a cosmetic bug. Everything else here is ordinary UI behaviour.
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const authState: { current: { user: unknown; isLoading: boolean } } = {
  current: { user: null, isLoading: false },
};
vi.mock("@/lib/auth", () => ({ useAuth: () => authState.current }));

import { ShowcaseSubscribeCta } from "@/components/showcase/subscribe-cta";
import { safeNextPath, withNext, DEFAULT_NEXT } from "@/lib/safe-next";

const LISTING = "11111111-2222-3333-4444-555555555555";

function mount(listingId: string | null, user: unknown = null, isLoading = false) {
  authState.current = { user, isLoading };
  return render(<ShowcaseSubscribeCta listingId={listingId} />);
}

// ═══════════════════════════════════════════════════════════════════════
// 1. 🔴 The open-redirect guard
// ═══════════════════════════════════════════════════════════════════════

describe("safeNextPath refuses to leave this site", () => {
  const REJECTED: [string | null | undefined, string][] = [
    ["https://evil.example/login", "absolute URL, different origin"],
    ["http://evil.example", "absolute URL"],
    ["//evil.example", "protocol-relative — browsers treat it as absolute"],
    ["/\\evil.example", "backslash form some parsers fold into //"],
    ["\\\\evil.example", "double backslash"],
    ["javascript:alert(1)", "a scheme, not a path"],
    ["evil.example", "no leading slash — resolves relative to the current page"],
    ["%2F%2Fevil.example", "percent-encoded protocol-relative"],
    ["", "empty"],
    [null, "null"],
    [undefined, "undefined"],
  ];

  it.each(REJECTED)("rejects %j (%s)", (input) => {
    expect(safeNextPath(input)).toBe(DEFAULT_NEXT);
  });

  it("rejects a control character smuggled in to break the check", () => {
    // Browsers strip \t and \n BEFORE parsing, so "/\t/evil.example" would
    // become "//evil.example" — protocol-relative — after our check if we
    // did not strip first.
    expect(safeNextPath("/\t/evil.example")).toBe(DEFAULT_NEXT);
    expect(safeNextPath("/\n/evil.example")).toBe(DEFAULT_NEXT);
  });

  it("rejects an ENCODED protocol-relative hidden behind a leading slash", () => {
    // "/%2F%2Fevil.example" looks same-site until something downstream
    // decodes it into "///evil.example". We decode FIRST so the check sees
    // the worst-case form, rather than trusting the router not to.
    expect(safeNextPath("/%2F%2Fevil.example")).toBe(DEFAULT_NEXT);
    expect(safeNextPath("/%2Fevil.example")).toBe(DEFAULT_NEXT);
  });

  it("rejects a malformed percent-escape rather than throwing", () => {
    expect(() => safeNextPath("%")).not.toThrow();
    expect(safeNextPath("%")).toBe(DEFAULT_NEXT);
  });

  it("ACCEPTS genuine same-site paths", () => {
    expect(safeNextPath("/marketplace/abc")).toBe("/marketplace/abc");
    expect(safeNextPath("/marketplace/me?sub=1")).toBe("/marketplace/me?sub=1");
    expect(safeNextPath("/a/b/c#frag")).toBe("/a/b/c#frag");
  });

  it("degrades to the fallback instead of erroring — a bad next must not block login", () => {
    expect(safeNextPath("https://evil.example", "/somewhere")).toBe("/somewhere");
  });
});

describe("withNext", () => {
  it("attaches an encoded next", () => {
    expect(withNext("/register", "/marketplace/abc")).toBe(
      "/register?next=%2Fmarketplace%2Fabc",
    );
  });

  it("omits next entirely when it would just be the default", () => {
    expect(withNext("/login", "/")).toBe("/login");
  });

  it("never propagates an unsafe destination", () => {
    expect(withNext("/register", "https://evil.example")).toBe("/register");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 2. The CTA itself
// ═══════════════════════════════════════════════════════════════════════

describe("the Subscribe CTA", () => {
  it("renders NOTHING when there is no published listing", () => {
    mount(null);
    expect(screen.queryByTestId("showcase-subscribe")).toBeNull();
    // and no disabled placeholder either — no control at all
    expect(screen.queryByText(/Subscribe/)).toBeNull();
  });

  it("sends a LOGGED-OUT visitor to register, with the way back", () => {
    mount(LISTING, null);
    const link = screen.getByTestId("showcase-subscribe");
    expect(link.getAttribute("data-authed")).toBe("no");
    expect(link.getAttribute("href")).toBe(
      `/register?next=${encodeURIComponent(`/marketplace/${LISTING}`)}`,
    );
  });

  it("sends a LOGGED-IN visitor straight to the listing", () => {
    mount(LISTING, { id: "u1" });
    const link = screen.getByTestId("showcase-subscribe");
    expect(link.getAttribute("data-authed")).toBe("yes");
    expect(link.getAttribute("href")).toBe(`/marketplace/${LISTING}`);
  });

  it("does not guess while the session is still resolving", () => {
    mount(LISTING, null, true);
    // no link at all — guessing wrong sends a logged-in user to a signup form
    expect(screen.queryByTestId("showcase-subscribe")).toBeNull();
    expect(screen.getByTestId("showcase-subscribe-loading")).toBeInTheDocument();
  });

  it("is data-driven, not hardcoded to s1", () => {
    const src = readFileSync(
      join(process.cwd(), "src/components/showcase/subscribe-cta.tsx"),
      "utf8",
    );
    const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
    expect(code).not.toMatch(/"s1"|'s1'/);
    expect(code).toContain("if (!listingId) return null;");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 3. The mask
// ═══════════════════════════════════════════════════════════════════════

describe("the mask holds on the public page", () => {
  it("the CTA names no instrument", () => {
    mount(LISTING, { id: "u1" });
    const text = screen.getByTestId("showcase-subscribe").textContent ?? "";
    expect(text).not.toMatch(/BSE|NIFTY|BANKNIFTY/i);
  });

  it("no strategy uuid prefix appears in the public showcase bundle", () => {
    const page = readFileSync(
      join(process.cwd(), "src/app/(public)/showcase/page.tsx"), "utf8");
    const cta = readFileSync(
      join(process.cwd(), "src/components/showcase/subscribe-cta.tsx"), "utf8");
    for (const src of [page, cta]) {
      expect(src).not.toContain("89423ecc");
      expect(src).not.toContain("0252e82c");
    }
  });
});
