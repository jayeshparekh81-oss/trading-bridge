/**
 * THE SWITCH-ON TRAP (founder, 26 Sep 2026): "the backend and frontend guided-path flags must
 * never be on separately. Make that impossible, not just documented — the frontend flag must
 * read the backend's own readiness and refuse to show the new path if the API is not live."
 *
 * This harness wires the REAL AuthProvider, the REAL dashboard layout, the REAL /start page,
 * the REAL /journey page, the REAL readiness hook and the REAL lib — only the HTTP client is
 * stood in (an in-memory server that answers /auth/me and the readiness call the way a real
 * backend would in each case). Where does a brand-new customer (onboarding_step 0) land?
 *
 *   FE flag OFF                         → /onboarding (and readiness is never even asked)
 *   FE ON  + BE OFF (readiness 404)     → /onboarding
 *   FE ON  + BE ON  (ready: true)       → /start
 *   FE ON  + readiness error / network  → /onboarding
 *   FE ON  + readiness TIMEOUT          → /onboarding (after the 3 s limit), never /start
 *   FE ON  + ready: false / wrong shape → /onboarding
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, waitFor, act, screen } from "@testing-library/react";
import { useSyncExternalStore } from "react";
import type { ReactNode } from "react";

// ── in-memory router ─────────────────────────────────────────────────
const routeState: { path: string; transitions: string[]; listeners: Set<() => void> } = {
  path: "/strategies",
  transitions: [],
  listeners: new Set(),
};
function navigate(to: string) {
  if (routeState.transitions.length >= 12) return;
  routeState.transitions.push(to);
  routeState.path = to;
  for (const l of routeState.listeners) l();
}
const subscribe = (l: () => void) => {
  routeState.listeners.add(l);
  return () => routeState.listeners.delete(l);
};
const getPath = () => routeState.path;
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: navigate, replace: navigate, refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => routeState.path,
  useSearchParams: () => new URLSearchParams(),
}));

// ── the in-memory backend ────────────────────────────────────────────
type Mode = "ready" | "be-off-404" | "error" | "network" | "timeout" | "not-ready" | "wrong-shape" | "html";
const server = { mode: "ready" as Mode, readinessCalls: 0, meStep: 0 };
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
  return {
    ApiError,
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
    api: {
      get: vi.fn(async (url: string) => {
        if (url === "/auth/me") {
          return {
            id: "u1", email: "new@x.com", full_name: "New", phone: null, is_active: true, is_admin: false,
            telegram_chat_id: null, notification_prefs: {}, created_at: "2026-08-01T00:00:00Z",
            onboarding_step: server.meStep, onboarding_completed_at: null,
          };
        }
        if (url === "/customer-lane/guided/readiness") {
          server.readinessCalls += 1;
          switch (server.mode) {
            case "ready": return { api: "guided-path", ready: true, missing: [] };
            case "not-ready": return { api: "guided-path", ready: false, missing: ["table customer_onboarding_drafts missing (migration 055 not applied)"] };
            case "wrong-shape": return { ready: true };
            case "html": return "<!doctype html><html></html>";
            case "be-off-404": throw new ApiError(404, "Not Found", { detail: "Not Found" });
            case "error": throw new ApiError(500, "Hamari taraf kuch gadbad hui.", { detail: "internal error" });
            case "network": throw new ApiError(0, "Internet ya server jawab nahi de raha.");
            case "timeout": return new Promise(() => { /* never answers */ });
          }
        }
        if (url === "/onboarding/state") {
          return { onboarding_step: 0, is_new_user: true, onboarding_completed_at: null, goal: null, experience: null };
        }
        throw new Error("unexpected GET " + url);
      }),
      put: vi.fn(async () => ({})),
      post: vi.fn(async () => ({})),
    },
  };
});

// ── chrome the pages mount, stubbed (not under test) ─────────────────
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() } }));
vi.mock("@/components/dashboard/sidebar", () => ({ Sidebar: () => null }));
vi.mock("@/components/dashboard/top-bar", () => ({ TopBar: () => null }));
vi.mock("@/components/dashboard/mobile-nav", () => ({ MobileNav: () => null }));
vi.mock("@/components/algomitra/ChatWidget", () => ({ ChatWidget: () => null }));
vi.mock("@/components/algomitra/AlgoMitraReactionLayer", () => ({ AlgoMitraReactionLayer: () => null }));
vi.mock("@/components/algomitra/always-on-panel", () => ({ AlwaysOnAlgoMitraPanelMount: () => null }));
vi.mock("@/hooks/use-algomitra-context", () => ({ useAlgoMitraPanelState: () => ({ isOpen: false }) }));
vi.mock("@/components/onboarding/OnboardingTour", () => ({ OnboardingTour: () => null }));
vi.mock("@/components/privacy-banner", () => ({ PrivacyBanner: () => null }));
vi.mock("@/shared/ui/skeleton-loader", () => ({ DashboardSkeleton: () => <div data-testid="skeleton" /> }));
vi.mock("@/components/simple/simple-shell", () => ({ SimpleShell: ({ children }: { children?: ReactNode }) => <div>{children}</div> }));
vi.mock("@/components/simple/pro-welcome-nudge", () => ({ ProWelcomeNudge: () => null }));
// The path itself is proven in guided-path.test.tsx; here we only ask WHETHER it is shown.
vi.mock("@/components/guided/guided-path", () => ({ GuidedPath: () => <div data-testid="guided-path-shown" /> }));
vi.mock("@/components/journey/journey-stepper", () => ({ JourneyStepper: () => <div data-testid="journey-stepper" /> }));
vi.mock("@/components/dashboard/pro-page", () => ({ ProPage: ({ children }: { children?: ReactNode }) => <div>{children}</div> }));

import { AuthProvider } from "@/lib/auth";
import { LadderProvider } from "@/hooks/useLadder";
import { LanguageProvider } from "@/contexts/LanguageContext";
import DashboardLayout from "@/app/(dashboard)/layout";
import StartPage from "@/app/start/page";
import JourneyPage from "@/app/(dashboard)/journey/page";
import * as lib from "@/lib/guided-path";

function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <LadderProvider>
        <LanguageProvider>{children}</LanguageProvider>
      </LadderProvider>
    </AuthProvider>
  );
}

function App() {
  const path = useSyncExternalStore(subscribe, getPath, getPath);
  // /onboarding and /start live OUTSIDE the (dashboard) route group in the real app, so once the
  // layout has sent the customer there it unmounts — model that, or the layout would redirect
  // again from a page it never renders (a harness artefact, not a product hop).
  if (path.startsWith("/onboarding") || path.startsWith("/start")) {
    return <div data-testid="left-dashboard">{path}</div>;
  }
  return (
    <DashboardLayout>
      <div data-testid="dashboard-page">{path}</div>
    </DashboardLayout>
  );
}

async function settle(ms = 300) {
  await act(async () => {
    await new Promise((r) => setTimeout(r, ms));
  });
}

async function landingOfANewCustomer(): Promise<string> {
  render(
    <Providers>
      <App />
    </Providers>,
  );
  await waitFor(() => expect(routeState.transitions.length).toBeGreaterThanOrEqual(1), { timeout: 6000 });
  await settle();
  expect(routeState.transitions).toHaveLength(1); // exactly one hop, wherever it goes
  return routeState.transitions[0];
}

beforeEach(() => {
  routeState.path = "/strategies";
  routeState.transitions = [];
  server.mode = "ready";
  server.readinessCalls = 0;
  server.meStep = 0;
  lib.resetGuidedReadinessCache();
  window.localStorage.setItem("tb_access_token", "t");
});
afterEach(() => {
  delete process.env[lib.GUIDED_FLAG];
  window.localStorage.clear();
});

describe("dashboard layout: a brand-new customer lands on the path ONLY when BOTH flags are live", () => {
  it("FE flag OFF → the current onboarding, and the backend is never even asked", async () => {
    server.mode = "ready";
    expect(await landingOfANewCustomer()).toMatch(/^\/onboarding/);
    expect(server.readinessCalls).toBe(0);
    expect(routeState.transitions).not.toContain("/start");
  }, 10_000);

  it("🔴 FE ON + BE OFF (readiness 404: the router is not mounted) → the current onboarding, never /start", async () => {
    process.env[lib.GUIDED_FLAG] = "1";
    server.mode = "be-off-404";
    expect(await landingOfANewCustomer()).toMatch(/^\/onboarding/);
    expect(server.readinessCalls).toBe(1);
    expect(routeState.transitions).not.toContain("/start");
  }, 10_000);

  it("FE ON + BE ON (ready: true) → /start", async () => {
    process.env[lib.GUIDED_FLAG] = "1";
    server.mode = "ready";
    expect(await landingOfANewCustomer()).toBe("/start");
    expect(routeState.transitions.filter((t) => t.startsWith("/onboarding"))).toEqual([]);
  }, 10_000);

  for (const mode of ["error", "network", "not-ready", "wrong-shape", "html"] as const) {
    it(`🔴 FE ON + readiness ${mode} → the current onboarding, never /start`, async () => {
      process.env[lib.GUIDED_FLAG] = "1";
      server.mode = mode;
      expect(await landingOfANewCustomer()).toMatch(/^\/onboarding/);
      expect(routeState.transitions).not.toContain("/start");
    }, 10_000);
  }

  it("🔴 FE ON + readiness TIMEOUT (never answers) → the current onboarding after the limit, never /start", async () => {
    process.env[lib.GUIDED_FLAG] = "1";
    server.mode = "timeout";
    render(
      <Providers>
        <App />
      </Providers>,
    );
    // while the backend has not answered, nobody is sent anywhere (a skeleton, not a guess)
    await settle(1000);
    expect(routeState.transitions).toEqual([]);
    expect(screen.queryByTestId("skeleton")).not.toBeNull();
    await waitFor(() => expect(routeState.transitions.length).toBe(1), { timeout: lib.READINESS_TIMEOUT_MS + 3000 });
    expect(routeState.transitions[0]).toMatch(/^\/onboarding/);
    expect(routeState.transitions).not.toContain("/start");
  }, 15_000);

  it("a customer who already finished onboarding is never redirected, whatever the flags", async () => {
    process.env[lib.GUIDED_FLAG] = "1";
    server.meStep = 6;
    render(
      <Providers>
        <App />
      </Providers>,
    );
    await screen.findByTestId("dashboard-page");
    await settle();
    expect(routeState.transitions).toEqual([]);
  }, 10_000);
});

describe("/start itself obeys the interlock (a direct visit or an old link)", () => {
  it("FE ON + BE ON → the path is shown", async () => {
    process.env[lib.GUIDED_FLAG] = "1";
    server.mode = "ready";
    render(<StartPage />);
    await screen.findByTestId("guided-path-shown");
    expect(routeState.transitions).toEqual([]);
  });

  it("🔴 FE ON + BE OFF, signed in → sent to the current onboarding; the path is never shown", async () => {
    process.env[lib.GUIDED_FLAG] = "1";
    server.mode = "be-off-404";
    render(<StartPage />);
    await screen.findByTestId("guided-not-ready");
    await waitFor(() => expect(routeState.transitions).toEqual(["/onboarding"]));
    expect(screen.queryByTestId("guided-path-shown")).toBeNull();
  });

  it("🔴 FE ON + readiness error, a visitor with no account → sent to /register (never a dead end)", async () => {
    process.env[lib.GUIDED_FLAG] = "1";
    server.mode = "error";
    window.localStorage.clear();
    render(<StartPage />);
    await waitFor(() => expect(routeState.transitions).toEqual(["/register"]));
    expect(screen.queryByTestId("guided-path-shown")).toBeNull();
    // the honest line with both ways forward stays on screen meanwhile
    expect(screen.getByTestId("guided-not-ready").querySelectorAll("a").length).toBe(2);
  });

  it("FE OFF → the honest line, no redirect, no readiness call", async () => {
    render(<StartPage />);
    expect(screen.getByTestId("guided-off")).toBeTruthy();
    await settle();
    expect(routeState.transitions).toEqual([]);
    expect(server.readinessCalls).toBe(0);
  });
});

describe("/journey points at the path only when it is live", () => {
  it("FE ON + BE ON → the 'Guided path kholo' door", async () => {
    process.env[lib.GUIDED_FLAG] = "1";
    server.mode = "ready";
    render(<JourneyPage />);
    await screen.findByTestId("journey-guided");
  });

  it("🔴 FE ON + BE OFF → no door to /start (the page as it was)", async () => {
    process.env[lib.GUIDED_FLAG] = "1";
    server.mode = "be-off-404";
    render(<JourneyPage />);
    await screen.findByTestId("journey-off");
    await settle();
    expect(screen.queryByTestId("journey-guided")).toBeNull();
  });
});

describe("the lib: only the exact ready shape is ready", () => {
  it("isReadyBody", () => {
    expect(lib.isReadyBody({ api: "guided-path", ready: true })).toBe(true);
    expect(lib.isReadyBody({ api: "guided-path", ready: false })).toBe(false);
    expect(lib.isReadyBody({ ready: true })).toBe(false);
    expect(lib.isReadyBody({ api: "guided-path", ready: "true" })).toBe(false);
    expect(lib.isReadyBody("<html>")).toBe(false);
    expect(lib.isReadyBody(null)).toBe(false);
  });

  it("guidedPathLive: flag off → false with no call; the answer is cached, not re-asked per page", async () => {
    expect(await lib.guidedPathLive()).toBe(false);
    expect(server.readinessCalls).toBe(0);
    process.env[lib.GUIDED_FLAG] = "1";
    server.mode = "ready";
    expect(await lib.guidedPathLive()).toBe(true);
    expect(await lib.guidedPathLive()).toBe(true);
    expect(server.readinessCalls).toBe(1);
  });

  it("fetchGuidedReadiness never rejects: timeout and errors are false", async () => {
    server.mode = "timeout";
    expect(await lib.fetchGuidedReadiness(50)).toBe(false);
    server.mode = "error";
    expect(await lib.fetchGuidedReadiness(50)).toBe(false);
  });
});
