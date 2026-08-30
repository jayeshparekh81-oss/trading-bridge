/**
 * The open-redirect guard INSIDE the auth context.
 *
 * Kept in its own file on purpose: the page-level tests mock "@/lib/auth"
 * wholesale, which hides whether the real context sanitises anything. And it
 * must, independently — `login()` is a public method on the context, so any
 * future caller can hand it an unchecked value, and that router.push happens
 * with a live session already in hand.
 *
 * Proven by mutation: replacing safeNextPath(next) with (next ?? "/") in
 * auth.tsx leaves every OTHER test in the suite green, and fails this one.
 */

import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status = 0;
    detail = "";
  }
  return {
    api: {
      post: vi.fn().mockResolvedValue({ access_token: "a", refresh_token: "r" }),
      get: vi.fn().mockResolvedValue({ id: "u1", email: "t@x.com" }),
    },
    ApiError,
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
  };
});

import { AuthProvider, useAuth } from "@/lib/auth";

function mountAuth() {
  return renderHook(() => useAuth(), {
    wrapper: ({ children }: { children: React.ReactNode }) => (
      <AuthProvider>{children}</AuthProvider>
    ),
  });
}

describe("the auth context sanitises `next` on its own", () => {
  it("🔴 never navigates off-site after login", async () => {
    push.mockClear();
    const { result } = mountAuth();

    await act(async () => {
      await result.current.login("t@x.com", "pw", "https://evil.example");
    });

    const pushed = push.mock.calls.map((c) => String(c[0]));
    expect(pushed.some((p) => p.includes("evil.example"))).toBe(false);
    expect(pushed).toContain("/");
  });

  it("🔴 never navigates off-site after register either", async () => {
    push.mockClear();
    const { result } = mountAuth();

    await act(async () => {
      await result.current.register(
        { email: "t@x.com", password: "pw", full_name: "T" },
        "//evil.example",
      );
    });

    const pushed = push.mock.calls.map((c) => String(c[0]));
    expect(pushed.some((p) => p.includes("evil.example"))).toBe(false);
  });

  it("DOES honour a genuine same-site destination", async () => {
    push.mockClear();
    const { result } = mountAuth();

    await act(async () => {
      await result.current.login("t@x.com", "pw", "/marketplace/abc");
    });

    expect(push.mock.calls.map((c) => String(c[0]))).toContain("/marketplace/abc");
  });

  it("still defaults to '/' when no next is given (unchanged behaviour)", async () => {
    push.mockClear();
    const { result } = mountAuth();

    await act(async () => {
      await result.current.login("t@x.com", "pw");
    });

    expect(push.mock.calls.map((c) => String(c[0]))).toContain("/");
  });
});
