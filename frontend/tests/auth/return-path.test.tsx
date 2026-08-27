/**
 * The return path: ?next= survives register/login and lands the customer back
 * on the strategy they were looking at.
 *
 * Before this, a logged-out visitor who clicked Subscribe got an error toast
 * ("Session expired. Please login again.") and, if they found their way to
 * register unaided, was dropped on a generic dashboard with no way back to the
 * thing they wanted. This is tested through the REAL pages, not a stand-in,
 * because the value of the feature is entirely in the wiring.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const login = vi.fn().mockResolvedValue(undefined);
const registerFn = vi.fn().mockResolvedValue(undefined);
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ login, register: registerFn, user: null, isLoading: false }),
}));

const search: { current: URLSearchParams } = { current: new URLSearchParams() };
vi.mock("next/navigation", () => ({
  useSearchParams: () => search.current,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/login",
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import LoginPage from "@/app/(auth)/login/page";

const TARGET = "/marketplace/11111111-2222-3333-4444-555555555555";

beforeEach(() => {
  vi.clearAllMocks();
  search.current = new URLSearchParams();
});

function fillAndSubmitLogin() {
  const inputs = document.querySelectorAll("input");
  fireEvent.change(inputs[0], { target: { value: "t@x.com" } });
  fireEvent.change(inputs[1], { target: { value: "pw" } });
  const form = document.querySelector("form");
  if (form) fireEvent.submit(form);
}

describe("login carries the return path", () => {
  it("passes ?next= through to the auth call", async () => {
    search.current = new URLSearchParams(`next=${encodeURIComponent(TARGET)}`);
    render(<LoginPage />);

    fillAndSubmitLogin();

    await waitFor(() => expect(login).toHaveBeenCalled());
    expect(login).toHaveBeenCalledWith("t@x.com", "pw", TARGET);
  });

  it("defaults to '/' when there is no next", async () => {
    render(<LoginPage />);
    fillAndSubmitLogin();
    await waitFor(() => expect(login).toHaveBeenCalled());
    expect(login.mock.calls[0][2]).toBe("/");
  });

  it("🔴 refuses an off-site next — never hands a fresh session to another origin", async () => {
    search.current = new URLSearchParams("next=https://evil.example");
    render(<LoginPage />);

    fillAndSubmitLogin();

    await waitFor(() => expect(login).toHaveBeenCalled());
    expect(login.mock.calls[0][2]).toBe("/");
    expect(login.mock.calls[0][2]).not.toContain("evil.example");
  });

  it("carries next across to the register link, so switching does not lose it", () => {
    search.current = new URLSearchParams(`next=${encodeURIComponent(TARGET)}`);
    render(<LoginPage />);

    const link = screen
      .getAllByRole("link")
      .find((a) => a.getAttribute("href")?.startsWith("/register"));

    expect(link?.getAttribute("href")).toBe(
      `/register?next=${encodeURIComponent(TARGET)}`,
    );
  });

  it("does not put an unsafe next on the register link either", () => {
    search.current = new URLSearchParams("next=//evil.example");
    render(<LoginPage />);

    const link = screen
      .getAllByRole("link")
      .find((a) => a.getAttribute("href")?.startsWith("/register"));

    expect(link?.getAttribute("href")).toBe("/register");
  });
});

describe("the pages still build as prerenderable", () => {
  it("both wrap useSearchParams in a Suspense boundary", async () => {
    const { readFileSync } = await import("node:fs");
    const { join } = await import("node:path");
    for (const p of [
      "src/app/(auth)/login/page.tsx",
      "src/app/(auth)/register/page.tsx",
    ]) {
      const src = readFileSync(join(process.cwd(), p), "utf8");
      // Without this, `next build` fails at prerender with
      // "useSearchParams() should be wrapped in a suspense boundary".
      // tsc and the dev server are both perfectly happy — only the build says.
      expect(src).toContain("<Suspense");
      expect(src).toContain("useSearchParams");
    }
  });
});
