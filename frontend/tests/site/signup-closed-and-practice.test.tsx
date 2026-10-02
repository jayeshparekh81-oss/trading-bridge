/**
 * 1 Oct 2026 (founder, REQUIREMENTS §13): "SIGNUP STAYS CLOSED to the public until the gate is
 * 8/8" + "paper demo only with the practice banner on every screen".
 *
 * The SERVER is the signup gate (POST /api/auth/register → 403 for anyone not invited); these
 * tests pin the courtesy half: no page invites a stranger to sign up unless the backend said,
 * live, {"open": true} (fail CLOSED on 404 / error / timeout / any other body), both signup
 * flows turn the server's 403 into the closed line, and the customer-path screens (/start,
 * /journey) carry the practice banner.
 */

// 2 Oct 2026: default is ENGLISH; this file pins HINGLISH words, so it describes an account that CHOSE Hinglish.
import "../i18n/hinglish-account";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const server = { status: "open" as "open" | "closed" | "404" | "error" | "hang" | "weird" };

vi.mock("@/shared/api/client", () => {
  class ApiError extends Error {
    status: number;
    detail: string;
    data: unknown;
    constructor(status: number, detail: string, data?: unknown) {
      super(detail);
      this.status = status;
      this.detail = detail;
      this.data = data;
    }
  }
  const get = vi.fn(async (url: string) => {
    if (url !== "/auth/signup-status") throw new ApiError(404, "Not Found");
    switch (server.status) {
      case "open": return { open: true, message: null };
      case "closed": return { open: false, message: "Abhi naye account band hain — jaldi khulenge." };
      case "404": throw new ApiError(404, "Not Found");
      case "error": throw new ApiError(500, "internal error");
      case "weird": return { open: "yes" };
      case "hang": return new Promise(() => undefined);
    }
  });
  return { api: { get, post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() }, ApiError };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/journey",
  useSearchParams: () => new URLSearchParams(),
}));

import { ApiError } from "@/shared/api/client";
import { SignupOrLogin } from "@/components/site/signup-or-login";
import { PracticeBanner, PRACTICE_PATH_LINE } from "@/components/site/practice-banner";
import { fetchSignupOpen, isOpenBody, resetSignupStatusCache, SIGNUP_CLOSED_LINE } from "@/lib/signup-status";
import { registerErrorHi } from "@/lib/auth-errors";
import { signupError } from "@/lib/guided-path";
import StartLayout from "@/app/start/layout";

beforeEach(() => {
  resetSignupStatusCache();
  server.status = "open";
});

describe("signup status — fail CLOSED", () => {
  it("only an exact {open: true} counts as open", () => {
    expect(isOpenBody({ open: true })).toBe(true);
    for (const b of [{ open: false }, { open: "yes" }, {}, null, "open", 1, [true]]) expect(isOpenBody(b)).toBe(false);
  });

  it.each(["closed", "404", "error", "weird"] as const)("backend %s → closed", async (s) => {
    server.status = s;
    await expect(fetchSignupOpen()).resolves.toBe(false);
  });

  it("a backend that never answers → closed after the timeout", async () => {
    server.status = "hang";
    await expect(fetchSignupOpen(50)).resolves.toBe(false);
  });

  it("open → open", async () => {
    await expect(fetchSignupOpen()).resolves.toBe(true);
  });
});

describe("SignupOrLogin — the site never invites a stranger", () => {
  it("closed → a Login link, never /register", async () => {
    server.status = "closed";
    render(<SignupOrLogin href="/register">Start Free</SignupOrLogin>);
    const link = await screen.findByText("Login karo");
    expect(link.closest("a")?.getAttribute("href")).toBe("/login");
    expect(screen.queryByText("Start Free")).toBeNull();
  });

  it("while checking → still no signup link (the first paint never invites)", () => {
    server.status = "hang";
    render(<SignupOrLogin href="/register">Start Free</SignupOrLogin>);
    expect(screen.queryByText("Start Free")).toBeNull();
    expect(document.querySelector('a[href="/register"]')).toBeNull();
  });

  it("open → the signup link", async () => {
    render(<SignupOrLogin href="/register">Start Free</SignupOrLogin>);
    await waitFor(() => expect(document.querySelector('a[href="/register"]')).not.toBeNull());
  });
});

describe("the server's 403 becomes the closed line in both signup flows", () => {
  const refused = new ApiError(403, "Abhi naye account band hain — jaldi khulenge. Agar aapko invite mila hai, to wahi email daaliye jis par invite aaya tha.");

  it("register page toast", () => {
    expect(registerErrorHi(refused)).toContain("band hain");
    expect(registerErrorHi(new ApiError(403, ""))).toBe(SIGNUP_CLOSED_LINE);
  });

  it("guided path signup step", () => {
    const e = signupError(refused);
    expect(e.kind).toBe("SIGNUP_CLOSED");
    expect(e.what_happened).toContain("band");
    expect(e.action?.href).toBe("/login?next=/start");
  });
});

describe("practice banner on the customer path", () => {
  it("the banner says it plainly and scopes itself to THIS path (never 'your BSE is paper')", () => {
    render(<PracticeBanner />);
    const b = screen.getByTestId("practice-banner");
    expect(b.textContent).toBe(PRACTICE_PATH_LINE);
    expect(PRACTICE_PATH_LINE).toMatch(/is raaste/);
    expect(PRACTICE_PATH_LINE).toMatch(/asli paisa nahi/);
  });

  it("/start renders it above every guided screen", () => {
    render(<StartLayout><p>screen</p></StartLayout>);
    expect(screen.getByTestId("practice-banner")).toBeTruthy();
  });

  it("every dashboard screen (/journey included) gets it from the ONE layout mount for customer accounts (source check)", async () => {
    // 2 Oct 2026: flipped forward. The original pinned `<PracticeBanner />` INSIDE journey/page.tsx;
    // the banner now comes from app/(dashboard)/layout.tsx for every non-admin account, so /journey
    // (and Ghar, Broker jodo, Orders, Sab band, Madad, Settings …) carry it without a second copy.
    // Original: expect(journeySrc).toMatch(/<PracticeBanner \/>/);
    const fs = await import("node:fs");
    const path = await import("node:path");
    const layout = fs.readFileSync(path.resolve(__dirname, "../../src/app/(dashboard)/layout.tsx"), "utf8");
    expect(layout).toMatch(/\{user && !user\.is_admin && <PracticeBanner sticky=\{false\} \/>\}/);
    const journey = fs.readFileSync(path.resolve(__dirname, "../../src/app/(dashboard)/journey/page.tsx"), "utf8");
    expect(journey).not.toMatch(/<PracticeBanner \/>/);
  });
});

describe("no page links to /register except through SignupOrLogin (or the closed-aware login/card)", () => {
  it("source scan", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const root = path.resolve(__dirname, "../../src");
    const offenders: string[] = [];
    const walk = (d: string) => {
      for (const e of fs.readdirSync(d, { withFileTypes: true })) {
        const p = path.join(d, e.name);
        if (e.isDirectory()) walk(p);
        else if (/\.tsx?$/.test(e.name)) {
          const s = fs.readFileSync(p, "utf8");
          if (/<Link\b[^>]*?href=\{?["`]\/register["`]/.test(s.replace(/\n/g, " ")) || /router\.(push|replace)\(["`]\/register/.test(s)) offenders.push(path.relative(root, p));
        }
      }
    };
    walk(root);
    expect(offenders).toEqual([]);
  });
});
