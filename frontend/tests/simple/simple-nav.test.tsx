/**
 * 🔴 "Jaane ka rasta nahi" (founder, 2026-09-05): in Simple mode, Settings had
 * no way back and browser back did not return him.
 *
 * This harness wires the REAL AuthProvider, LadderProvider, LanguageProvider,
 * the REAL (dashboard) layout (SimpleShell / Pro chrome), the REAL
 * SimpleHome and the REAL ModeCard through an in-memory router that keeps a
 * history stack, so both "‹ Wapas" and the browser's back button can be
 * exercised and every redirect counted.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor, act, screen, fireEvent } from "@testing-library/react";
import { useSyncExternalStore } from "react";
import type { ReactNode } from "react";

// ── in-memory router with a history stack ────────────────────────────
const R: { hist: string[]; transitions: string[]; listeners: Set<() => void> } = { hist: ["/"], transitions: [], listeners: new Set() };
const MAX_HOPS = 12;
function notify() {
  for (const l of R.listeners) l();
}
function push(to: string) {
  if (R.transitions.length >= MAX_HOPS) return;
  R.transitions.push(`push:${to}`);
  R.hist.push(to);
  notify();
}
function replace(to: string) {
  if (R.transitions.length >= MAX_HOPS) return;
  R.transitions.push(`replace:${to}`);
  R.hist[R.hist.length - 1] = to;
  notify();
}
/** The browser's back button: pops history, notifies usePathname. Not a redirect. */
function browserBack() {
  if (R.hist.length > 1) R.hist.pop();
  notify();
}
const path = () => R.hist[R.hist.length - 1];
const subscribe = (l: () => void) => {
  R.listeners.add(l);
  return () => R.listeners.delete(l);
};
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace, back: browserBack, refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => path(),
  useSearchParams: () => new URLSearchParams(),
}));

// ── server ───────────────────────────────────────────────────────────
const server = { createdAt: "2026-09-06T08:00:00Z", prefs: {} as Record<string, unknown>, meCalls: 0, brokerConnected: false };
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
            email: "walk@x.com",
            full_name: "Ramesh Test",
            phone: null,
            is_active: true,
            is_admin: false,
            telegram_chat_id: null,
            notification_prefs: server.prefs,
            created_at: server.createdAt,
            onboarding_step: 6,
            onboarding_completed_at: "2026-09-05T00:00:01Z",
          };
        }
        if (url.startsWith("/brokers/dhan/status")) return { connected: server.brokerConnected, expires_estimate: null };
        if (url.startsWith("/users/me/brokers")) return [];
        if (url.startsWith("/marketplace/subscriptions/signals")) return { signals: [] };
        if (url.startsWith("/marketplace/subscriptions/me")) return { subscriptions: [] };
        if (url.startsWith("/strategies")) return { strategies: [] };
        return {};
      }),
      put: vi.fn(async (_url: string, body: { notification_prefs?: Record<string, unknown> }) => {
        if (body?.notification_prefs) server.prefs = body.notification_prefs;
        return {};
      }),
      post: vi.fn(async () => ({})),
      patch: vi.fn(async () => ({})),
    },
  };
});
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }) }));

// ── Pro chrome stubs; the sidebar stub records the expand-once event ──
const sidebar = { expandEvents: 0 };
vi.mock("@/components/dashboard/sidebar", async () => {
  const React = await import("react");
  return {
    Sidebar: () => {
      React.useEffect(() => {
        const on = () => {
          sidebar.expandEvents += 1;
        };
        window.addEventListener("tradetri:sidebar-expand", on);
        return () => window.removeEventListener("tradetri:sidebar-expand", on);
      }, []);
      return <nav data-testid="pro-sidebar" />;
    },
  };
});
vi.mock("@/components/dashboard/top-bar", () => ({ TopBar: () => null }));
vi.mock("@/components/dashboard/mobile-nav", () => ({ MobileNav: () => null }));
vi.mock("@/components/algomitra/ChatWidget", () => ({ ChatWidget: () => null }));
vi.mock("@/components/algomitra/AlgoMitraReactionLayer", () => ({ AlgoMitraReactionLayer: () => null }));
vi.mock("@/components/algomitra/always-on-panel", () => ({ AlwaysOnAlgoMitraPanelMount: () => null }));
vi.mock("@/hooks/use-algomitra-context", () => ({ useAlgoMitraPanelState: () => ({ isOpen: false }) }));
vi.mock("@/components/onboarding/OnboardingTour", () => ({ OnboardingTour: () => <div data-testid="pro-tour" /> }));
vi.mock("@/components/privacy-banner", () => ({ PrivacyBanner: () => null }));
vi.mock("@/components/ui/skeleton-loader", () => ({ DashboardSkeleton: () => <div data-testid="skeleton" /> }));
vi.mock("@/components/logo", () => ({ Logo: () => null }));
vi.mock("framer-motion", () => ({
  motion: new Proxy({}, { get: () => (props: Record<string, unknown> & { children?: ReactNode }) => {
    const { children, ...rest } = props;
    const dom = Object.fromEntries(Object.entries(rest).filter(([k]) => /^(data-|aria-|className|role|id)/.test(k)));
    return <div {...dom}>{children}</div>;
  } }),
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  useReducedMotion: () => true,
}));

import { AuthProvider } from "@/lib/auth";
import { LadderProvider, useLadder } from "@/hooks/useLadder";
import { LanguageProvider } from "@/contexts/LanguageContext";
import DashboardLayout from "@/app/(dashboard)/layout";
import { SimpleHome } from "@/components/simple/simple-home";
import { toast } from "sonner";
import { LEARN_TILES, MAIN_TILES, TILE_ROUTE } from "@/lib/simple/level";
import { ModeCard } from "@/components/simple/mode-card";

// HomePage mirrors (dashboard)/page.tsx (SimpleHome for level < 4, else the Pro
// overview, stubbed here). A next/link click does not route in jsdom, so tile
// taps are simulated with push(href) after asserting the tile's href.
function HomePage() {
  const l = useLadder();
  return l.level < 4 ? <SimpleHome /> : <div data-testid="pro-home" />;
}
function App() {
  const p = useSyncExternalStore(subscribe, path, path);
  let page: ReactNode;
  if (p === "/") page = <HomePage />;
  else if (p === "/settings") page = <div data-testid="settings-page"><ModeCard /></div>;
  else page = <div data-testid="page">{p}</div>;
  return <DashboardLayout>{page}</DashboardLayout>;
}
function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <LadderProvider>
        <LanguageProvider>{children}</LanguageProvider>
      </LadderProvider>
    </AuthProvider>
  );
}
const settle = () => act(async () => { await new Promise((r) => setTimeout(r, 350)); });

beforeEach(() => {
  R.hist = ["/"];
  R.transitions = [];
  server.createdAt = "2026-09-06T08:00:00Z";
  server.prefs = {};
  server.meCalls = 0;
  server.brokerConnected = false;
  sidebar.expandEvents = 0;
  window.localStorage.clear();
  window.localStorage.setItem("tb_access_token", "t");
  vi.mocked(toast.info).mockClear();
});

/** Every main tile and every "Aur seekhein" tile: opens its page (no gate), "‹ Wapas" returns home in one tap. */
async function everyTileOpensAndWapasReturns() {
  const targets = [
    ...MAIN_TILES.map((id) => ({ testid: `tile-${id}`, href: TILE_ROUTE[id] })),
    ...LEARN_TILES.filter((id) => id !== "pro").map((id) => ({ testid: `learn-${id}`, href: TILE_ROUTE[id as "templates" | "build"] })),
  ];
  expect(targets).toHaveLength(6);
  for (const { testid, href } of targets) {
    expect((screen.getByTestId(testid) as HTMLAnchorElement).getAttribute("href")).toBe(href);
    R.transitions = [];
    act(() => push(href)); // the tap
    await waitFor(() => expect(screen.getByTestId("page")).toHaveTextContent(href));
    const back = screen.getByTestId("shell-back");
    expect(back).toHaveTextContent("Wapas");
    fireEvent.click(back);
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    await settle();
    expect(R.transitions).toEqual([`push:${href}`, "push:/"]);
  }
}

describe("NO LOCKS — a fresh account with zero actions can reach everything", () => {
  it("every main tile and every 'Aur seekhein' tile opens its page, and ‹ Wapas returns home in one tap", async () => {
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    // D: AlgoMitra's first-visit nudge, once, in the settled language.
    await waitFor(() => expect(vi.mocked(toast.info)).toHaveBeenCalledWith(expect.stringContaining("char kaam upar"), expect.anything()));
    expect(vi.mocked(toast.info)).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("simple-home").textContent).not.toMatch(/🔒|khulega/);
    expect(screen.getByTestId("learn-hint")).toHaveTextContent("Pehle upar wale 4 karo, phir yeh — aaram se.");
    await everyTileOpensAndWapasReturns();
    expect(vi.mocked(toast.info)).toHaveBeenCalledTimes(1); // the home nudge did not re-fire on any of the six returns
  }, 20_000);

  it("a Simple account further along the journey (step 3) reaches everything the same way", async () => {
    const T = "2026-09-06T09:00:00Z";
    server.prefs = { _ui_ladder: { earned: 1, choice: "auto", facts: { brokerConnected: T, hasSubscription: T, firstSignalSeen: T, templateCloned: T, backtestRun: T }, proNudgeSeen: false, simpleOnboardingDone: true, homeNudgeSeen: true, tipsShown: [] } };
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("simple-home")).toHaveAttribute("data-level", "3"));
    // waits for the Hinglish flip (the provider's default is English for one render)
    await waitFor(() => expect(screen.getByTestId("progress-line")).toHaveTextContent("Aapka safar: 3 / 4 kadam"));
    await everyTileOpensAndWapasReturns();
  }, 25_000);

  it("Pro-only surfaces are open in Simple too — by URL and by browser back — never a gate", async () => {
    R.hist = ["/", "/analytics", "/settings"]; // history from earlier
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("mode-card")).toBeInTheDocument());
    R.transitions = [];
    act(() => browserBack());
    await waitFor(() => expect(screen.getByTestId("page")).toHaveTextContent("/analytics"));
    // sentinel: the deleted gate page's testid must never come back
    expect(screen.queryByTestId("level-gate")).toBeNull();
    expect(screen.getByTestId("shell-back")).toHaveTextContent("Wapas");
    const proOnly = ["/chart", "/strategies/indicators", "/webhooks", "/compliance"];
    for (const href of proOnly) {
      act(() => push(href));
      await waitFor(() => expect(screen.getByTestId("page")).toHaveTextContent(href));
      expect(screen.getByTestId("shell-back")).toHaveTextContent("Wapas");
    }
    await settle();
    // exactly the four taps — no redirect of any kind, push or replace
    expect(R.transitions).toEqual(proOnly.map((h) => `push:${h}`));
    fireEvent.click(screen.getByTestId("shell-back"));
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
  }, 20_000);

  it("first tap on an 'Aur seekhein' tile: AlgoMitra explains it in one line, once per tile", async () => {
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("learn-templates")).toBeInTheDocument());
    await waitFor(() => expect(vi.mocked(toast.info)).toHaveBeenCalledTimes(1)); // the first-visit nudge
    fireEvent.click(screen.getByTestId("learn-templates"));
    await waitFor(() => expect(vi.mocked(toast.info)).toHaveBeenCalledWith(expect.stringContaining("taiyar strategies"), expect.anything()));
    fireEvent.click(screen.getByTestId("learn-templates"));
    await settle();
    expect(vi.mocked(toast.info)).toHaveBeenCalledTimes(2); // not a third time
    fireEvent.click(screen.getByTestId("learn-build"));
    await waitFor(() => expect(vi.mocked(toast.info)).toHaveBeenCalledWith(expect.stringContaining("apni strategy khud"), expect.anything()));
    await waitFor(() => expect((server.prefs._ui_ladder as { tipsShown: string[] }).tipsShown).toEqual(["templates", "build"]));
  }, 20_000);
});

describe("a way back from every screen", () => {
  it("‹ Wapas on Settings returns home in one tap; the browser's back button also returns home with zero redirects", async () => {
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    R.transitions = [];
    act(() => push("/settings"));
    await waitFor(() => expect(screen.getByTestId("mode-card")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("shell-back"));
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    await settle();
    expect(R.transitions).toEqual(["push:/settings", "push:/"]);
    act(() => push("/settings"));
    await waitFor(() => expect(screen.getByTestId("mode-card")).toBeInTheDocument());
    R.transitions = [];
    act(() => browserBack());
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    await settle();
    expect(R.transitions).toEqual([]);
    expect(path()).toBe("/");
  }, 20_000);
});

describe("Simple ⇄ Pro switching never dead-ends", () => {
  it("a Pro account toggling Simple in Settings LANDS on the Simple home, journey line from its real state", async () => {
    server.createdAt = "2026-03-01T00:00:00Z"; // existing → Pro
    server.brokerConnected = true;
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("pro-home")).toBeInTheDocument());
    expect(screen.getByTestId("pro-tour")).toBeInTheDocument(); // an existing Pro account keeps its tour
    act(() => push("/settings"));
    await waitFor(() => expect(screen.getByTestId("mode-card")).toBeInTheDocument());
    R.transitions = [];
    fireEvent.click(screen.getByTestId("mode-simple"));
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    await settle();
    expect(R.transitions).toEqual(["push:/"]);
    expect(screen.queryByTestId("pro-sidebar")).toBeNull();
    await waitFor(() => expect(screen.getByTestId("progress-line")).toHaveTextContent("Agla: Strategy chuno")); // broker already done
    expect(screen.getByTestId("learn-templates")).toHaveAttribute("href", "/strategies/templates");
    expect(screen.getByTestId("pro-entry")).toBeInTheDocument();
  }, 20_000);

  it("toggling Pro in Settings lands on the Pro dashboard immediately, sidebar expanded once, nudge shown, no tour on top", async () => {
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    act(() => push("/settings"));
    await waitFor(() => expect(screen.getByTestId("mode-card")).toBeInTheDocument());
    R.transitions = [];
    fireEvent.click(screen.getByTestId("mode-pro"));
    await waitFor(() => expect(screen.getByTestId("pro-home")).toBeInTheDocument());
    await settle();
    expect(R.transitions).toEqual(["push:/"]);
    expect(screen.getByTestId("pro-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("pro-welcome-nudge")).toBeInTheDocument();
    expect(sidebar.expandEvents).toBeGreaterThanOrEqual(1);
    expect(screen.queryByTestId("simple-shell")).toBeNull();
    expect(screen.queryByTestId("pro-tour")).toBeNull();
  }, 20_000);

  it("the Pro tile under 'Aur seekhein' and the Pro card are one tap into Pro", async () => {
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("learn-pro")).toBeInTheDocument());
    await waitFor(() => expect(vi.mocked(toast.info)).toHaveBeenCalledTimes(1)); // the language has settled (Hinglish)
    fireEvent.click(screen.getByTestId("learn-pro"));
    await waitFor(() => expect(screen.getByTestId("pro-home")).toBeInTheDocument());
    expect(screen.getByTestId("pro-welcome-nudge")).toBeInTheDocument();
    await waitFor(() => expect(vi.mocked(toast.info)).toHaveBeenCalledWith(expect.stringContaining("poora menu"), expect.anything()));
  }, 20_000);
});
