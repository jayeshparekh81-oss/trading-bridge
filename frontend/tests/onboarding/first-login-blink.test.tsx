/**
 * 🔴 First-login blink (2026-09-05): the whole site flickered continuously
 * right after a new customer finished (or skipped) onboarding.
 *
 * The loop: POST /onboarding/complete flips the SERVER's onboarding_step to 6,
 * but the in-memory `user` in the auth context still says 0. The next client
 * navigation mounts the (dashboard) layout, which reads the stale 0 and
 * router.replace("/onboarding"); /onboarding asks GET /onboarding/state, learns
 * is_new_user=false, and router.replace("/strategies"); the layout runs again
 * with the same stale 0 … forever, at the speed of one fetch per hop.
 *
 * This harness wires the REAL AuthProvider, the REAL dashboard layout and the
 * REAL onboarding page through an in-memory router and counts every redirect.
 * A single hop each way is legitimate; anything above that is the blink.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor, act } from "@testing-library/react";
import { useSyncExternalStore } from "react";
import type { ReactNode } from "react";

// ── in-memory router ─────────────────────────────────────────────────
const routeState: { path: string; transitions: string[]; listeners: Set<() => void> } = {
  path: "/strategies",
  transitions: [],
  listeners: new Set(),
};
const MAX_HOPS = 12; // stop a runaway loop so the test terminates
function navigate(to: string) {
  if (routeState.transitions.length >= MAX_HOPS) return;
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

// ── server: /auth/me is stale (0) until re-fetched; /onboarding/state is the truth (6) ──
// `flipOnState`: the moment the onboarding page asks for state, the server has
// already moved on to step 6 (the customer completed/skipped) — the auth
// context still holds the pre-completion /auth/me until someone refreshes it.
// `createdAt`: an EXISTING account (before the ladder launched, 2026-09-05) is
// Pro and sees the 5-step onboarding; a NEW signup is Level 1 and sees the
// 3-step Simple onboarding. Both paths must hold the one-hop rule.
const server = { meStep: 0, meCalls: 0, stateCalls: 0, flipOnState: false, createdAt: "2026-08-01T00:00:00Z", prefs: {} as Record<string, unknown> };
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status = 0;
    detail = "";
    data: unknown = undefined;
  }
  return {
    ApiError,
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
    api: {
      get: vi.fn(async (url: string) => {
        if (url === "/auth/me") {
          server.meCalls += 1;
          return {
            id: "u1",
            email: "new@x.com",
            full_name: "New",
            phone: null,
            is_active: true,
            is_admin: false,
            telegram_chat_id: null,
            notification_prefs: server.prefs,
            created_at: server.createdAt,
            onboarding_step: server.meStep,
            onboarding_completed_at: server.meStep === 6 ? "2026-09-05T00:00:01Z" : null,
          };
        }
        if (url === "/onboarding/state") {
          server.stateCalls += 1;
          if (server.flipOnState) server.meStep = 6;
          return {
            onboarding_step: 6,
            is_new_user: false,
            onboarding_completed_at: "2026-09-05T00:00:01Z",
            goal: null,
            experience: null,
          };
        }
        throw new Error("unexpected GET " + url);
      }),
      put: vi.fn(async (_url: string, body: { notification_prefs?: Record<string, unknown> }) => {
        // the level ladder persists itself here (read-merge-write)
        if (body?.notification_prefs) server.prefs = body.notification_prefs;
        return {};
      }),
      post: vi.fn(async (url: string) => {
        if (url === "/onboarding/complete") {
          server.meStep = 6;
          return { onboarding_step: 6, is_new_user: false, onboarding_completed_at: "x", goal: null, experience: null };
        }
        return {};
      }),
    },
  };
});

// ── chrome the layout mounts, stubbed (not under test) ──────────────
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
vi.mock("@/components/ui/skeleton-loader", () => ({ DashboardSkeleton: () => <div data-testid="skeleton" /> }));
vi.mock("@/components/onboarding/progress-indicator", () => ({ ProgressIndicator: () => null }));
vi.mock("@/components/onboarding/skip-button", () => ({ SkipButton: () => null }));
vi.mock("@/components/logo", () => ({ Logo: () => null }));
vi.mock("@/lib/analytics", () => ({ trackEventSync: vi.fn() }));
vi.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => (props: { children?: ReactNode }) => <div>{props.children}</div> }),
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  useReducedMotion: () => true,
}));

import { AuthProvider } from "@/lib/auth";
import { LadderProvider } from "@/hooks/useLadder";
import { LanguageProvider } from "@/contexts/LanguageContext";
import DashboardLayout from "@/app/(dashboard)/layout";
import OnboardingLayout from "@/app/onboarding/layout";
import OnboardingPage from "@/app/onboarding/page";

function Providers({ children }: { children: ReactNode }) {
  // The same nesting as components/providers.tsx (auth → ladder → language).
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
  if (path.startsWith("/onboarding")) {
    return (
      <OnboardingLayout>
        <OnboardingPage />
      </OnboardingLayout>
    );
  }
  return (
    <DashboardLayout>
      <div data-testid="dashboard-page">{path}</div>
    </DashboardLayout>
  );
}

beforeEach(() => {
  routeState.path = "/strategies";
  routeState.transitions = [];
  server.meStep = 0;
  server.meCalls = 0;
  server.stateCalls = 0;
  server.flipOnState = false;
  server.createdAt = "2026-08-01T00:00:00Z";
  server.prefs = {};
  window.localStorage.setItem("tb_access_token", "t");
});

describe("first-login blink: dashboard layout ⇄ /onboarding", () => {
  it("🔴 a customer whose onboarding just completed is NOT bounced back and forth", async () => {
    render(
      <Providers>
        <App />
      </Providers>,
    );
    // The provider loads the STALE /auth/me (step 0) exactly as the browser
    // had it while the customer was still onboarding …
    await waitFor(() => expect(server.meCalls).toBeGreaterThanOrEqual(1));
    // … and the server has since moved on (the customer clicked Skip / the
    // step-5 CTA in the onboarding page, which POSTed /onboarding/complete).
    server.meStep = 6;

    // Let the guards run for a while. Before the fix this loops until MAX_HOPS.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 400));
    });

    const hopsToOnboarding = routeState.transitions.filter((t) => t === "/onboarding").length;
    // One hop into /onboarding is the legitimate case (the layout could not
    // know yet); a SECOND one is the blink.
    expect(hopsToOnboarding).toBeLessThanOrEqual(1);
    expect(routeState.transitions.length).toBeLessThanOrEqual(2);
    // The loop is broken by re-reading the server's truth, not by a timer.
    expect(server.meCalls).toBeGreaterThanOrEqual(2);
    expect(routeState.path).not.toBe("/onboarding");
  }, 10_000);

  it("🔴 completing onboarding refreshes the auth user before leaving the page", async () => {
    routeState.path = "/onboarding";
    server.flipOnState = true;
    render(
      <Providers>
        <App />
      </Providers>,
    );
    await waitFor(() => expect(server.meCalls).toBeGreaterThanOrEqual(1));
    // /onboarding/state for a genuinely new user would show the flow; here
    // the fixture's state endpoint says "done" (is_new_user=false), which is
    // exactly the stale-context shape. The page must refresh the auth user
    // BEFORE bouncing, so the layout it lands on agrees with the server.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 400));
    });
    expect(server.meCalls).toBeGreaterThanOrEqual(2);
    expect(routeState.transitions.filter((t) => t === "/onboarding").length).toBe(0);
    expect(routeState.transitions.length).toBeLessThanOrEqual(1);
    expect(routeState.path).toBe("/strategies");
  }, 10_000);

  it("🔴 the 3-step Simple onboarding (new signup) holds the one-hop rule too", async () => {
    server.createdAt = "2026-09-06T08:00:00Z"; // signed up after the ladder launched → Level 1
    routeState.path = "/onboarding";
    render(
      <Providers>
        <App />
      </Providers>,
    );
    await waitFor(() => expect(server.meCalls).toBeGreaterThanOrEqual(1));
    // A NEW signup gets the Simple flow, not the 5-step one.
    const ob = await waitFor(() => {
      const el = document.querySelector('[data-testid="simple-onboarding"]');
      if (!el) throw new Error("simple onboarding not shown");
      return el as HTMLElement;
    });
    expect(ob.dataset.step).toBe("1");
    // "Baad mein" (skip all): POST /onboarding/complete → refresh the auth user → go home.
    await act(async () => {
      (document.querySelector('[data-testid="ob-skip-all"]') as HTMLButtonElement).click();
      await new Promise((r) => setTimeout(r, 400));
    });
    expect(server.meStep).toBe(6);
    expect(server.meCalls).toBeGreaterThanOrEqual(2); // refreshed BEFORE leaving
    expect(routeState.transitions).toEqual(["/"]); // exactly one hop, home
    expect(routeState.transitions.filter((t) => t === "/onboarding").length).toBe(0);
    // …and the dashboard layout that receives them is the Simple chrome, level 1.
    await waitFor(() => expect(document.querySelector('[data-testid="simple-shell"]')).not.toBeNull());
    expect((document.querySelector('[data-testid="simple-shell"]') as HTMLElement).dataset.level).toBe("1");
    // The ladder persisted itself once for the new account, without clobbering other prefs.
    expect(server.prefs._ui_ladder).toMatchObject({ earned: 1, simpleOnboardingDone: true });
    // Nothing looped afterwards.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 300));
    });
    expect(routeState.transitions).toEqual(["/"]);
  }, 10_000);
});
