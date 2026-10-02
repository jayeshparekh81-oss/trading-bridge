/**
 * /login and /register must render on the SERVER (StrykeX Stage-1 audit, 2 Oct 2026).
 *
 * MEASURED on the served build 67a3e41e: the HTML of both pages was an EMPTY shell —
 * `<template data-dgst="BAILOUT_TO_CLIENT_SIDE_RENDERING">` + the footer disclaimer. A customer
 * on a phone saw a blank screen until ~285 KB (gzip) of JavaScript had arrived and run. Cause:
 * `useSearchParams()` forces a client-side bailout up to the nearest <Suspense>, and both pages
 * wrapped their WHOLE page in `<Suspense fallback={null}>`.
 *
 * The fix: the ONE `useSearchParams()` call lives in <ReturnPathProbe> inside its own Suspense.
 * These tests make the probe THROW during a server render (what Next's bailout does) and assert the
 * page around it still comes out of `renderToString` — the title, the form and the way back are in
 * the first byte. On the old code the same render produced NOTHING but the fallback.
 */

import { describe, it, expect, vi } from "vitest";
import { renderToString } from "react-dom/server";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

vi.mock("@/hooks/useSignupOpen", () => ({ useSignupOpen: () => "closed" }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ login: vi.fn(), register: vi.fn(), user: null, isLoading: false, isAuthenticated: false }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));
// What Next does during a static render: the hook throws a bailout up to the nearest Suspense.
vi.mock("next/navigation", () => ({
  useSearchParams: () => {
    throw new Error("BAILOUT_TO_CLIENT_SIDE_RENDERING (simulated)");
  },
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/login",
}));

import LoginPage from "@/app/(auth)/login/page";
import RegisterPage from "@/app/(auth)/register/page";

const quiet = () => {
  // react-dom/server reports the recoverable error inside the Suspense boundary to console.error
  const spy = vi.spyOn(console, "error").mockImplementation(() => {});
  return () => spy.mockRestore();
};

describe("the first byte of HTML carries the screen (no page-wide client-side bailout)", () => {
  it("/login: title, form and the way back are server-rendered even when the ?next= reader bails out", () => {
    const restore = quiet();
    try {
      const html = renderToString(<LoginPage />);
      expect(html).toContain("Login karo");
      expect(html).toMatch(/<form/);
      expect(html).toMatch(/type="email"|name="email"/);
      // signup is CLOSED on the live site today: the closed line, not a register link
      expect(html).toContain("Abhi naye account band hain");
    } finally {
      restore();
    }
  });

  it("/register: title and form are server-rendered even when the ?next= reader bails out", () => {
    const restore = quiet();
    try {
      const html = renderToString(<RegisterPage />);
      expect(html).toContain("Naya account banao");
      // the register screen is fields + a button (no <form> element): the fields must be there
      expect(html).toMatch(/type="email"/);
      expect(html).toMatch(/type="password"/);
      expect(html).toContain("Account banao (free)");
      expect(html).toContain("Abhi naye account sirf invite se bante hain");
    } finally {
      restore();
    }
  });

  it("neither page wraps itself in a Suspense boundary, and only the probe reads the search params (source)", () => {
    for (const f of ["src/app/(auth)/login/page.tsx", "src/app/(auth)/register/page.tsx"]) {
      const src = readFileSync(resolve(__dirname, "../../", f), "utf8");
      // no import of the hook and no call of it — a comment may name it, the code may not
      expect(src, f).not.toMatch(/import \{[^}]*useSearchParams[^}]*\} from "next\/navigation"/);
      expect(src, f).not.toMatch(/useSearchParams\(\)\.get\(/);
      // the default export returns the inner page directly — no page-wide Suspense
      expect(src, f).toMatch(/export default function \w+Page\(\) \{\s*return <\w+PageInner \/>;\s*\}/);
      expect(src, f).toMatch(/<ReturnPathProbe onPath=\{setNextPath\} \/>/);
    }
    const probe = readFileSync(resolve(__dirname, "../../src/components/auth/return-path-probe.tsx"), "utf8");
    expect(probe).toMatch(/useSearchParams\(\)\.get\("next"\)/);
    expect(probe).toMatch(/safeNextPath\(/);
  });

  it("no unbacked badge on the auth footers ('PRODUCTION GRADE' was a claim nothing measured)", () => {
    for (const f of ["src/app/(auth)/login/page.tsx", "src/app/(auth)/register/page.tsx"]) {
      const src = readFileSync(resolve(__dirname, "../../", f), "utf8");
      expect(src, f).not.toMatch(/PRODUCTION GRADE/);
    }
  });
});
