/**
 * 🔴 "Jaane ka rasta nahi" (founder, 2026-09-05): in Simple mode, Settings had
 * no way back and browser back did not return him.
 *
 * This harness wires the REAL AuthProvider, LadderProvider, LanguageProvider,
 * the REAL (dashboard) layout (SimpleShell / Pro chrome / gate), the REAL
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
import { ModeCard } from "@/components/simple/mode-card";

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
const tileHref = (id: string) => (screen.getByTestId(`tile-${id}`) as HTMLAnchorElement).getAttribute("href")!;

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

describe("Simple mode — a way back from every screen", () => {
  it("‹ Wapas on every tile target and on Settings returns to the home in ONE tap, no redirects", async () => {
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    // D: AlgoMitra's first-visit nudge explains the ladder in one sentence, once.
    await waitFor(() => expect(vi.mocked(toast.info)).toHaveBeenCalledWith(expect.stringContaining("naye button khulenge"), expect.anything()));
    expect(vi.mocked(toast.info)).toHaveBeenCalledTimes(1);
    for (const id of ["strategy", "broker", "signals", "help"]) {
      const href = tileHref(id);
      R.transitions = [];
      act(() => push(href)); // the tile tap
      await waitFor(() => expect(screen.getByTestId("page")).toHaveTextContent(href));
      const back = screen.getByTestId("shell-back");
      expect(back).toHaveTextContent("Wapas");
      fireEvent.click(back);
      await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
      await settle();
      expect(R.transitions).toEqual([`push:${href}`, "push:/"]);
    }
    // Settings too — the exact dead end the founder hit
    R.transitions = [];
    act(() => push("/settings"));
    await waitFor(() => expect(screen.getByTestId("mode-card")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("shell-back"));
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    await settle();
    expect(R.transitions).toEqual(["push:/settings", "push:/"]);
  }, 15_000);

  it("the browser's back button also returns home from Settings, and nothing redirects afterwards", async () => {
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    act(() => push("/settings"));
    await waitFor(() => expect(screen.getByTestId("mode-card")).toBeInTheDocument());
    R.transitions = [];
    act(() => browserBack());
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    await settle();
    expect(R.transitions).toEqual([]); // the redirect counter: zero after a back
    expect(path()).toBe("/");
  }, 15_000);

  it("a Pro-only page reached by browser back shows the gate IN PLACE (no redirect), with Ghar one tap away", async () => {
    R.hist = ["/", "/analytics", "/settings"]; // history from the Pro days
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("mode-card")).toBeInTheDocument());
    R.transitions = [];
    act(() => browserBack());
    await waitFor(() => expect(screen.getByTestId("level-gate")).toBeInTheDocument());
    await settle();
    expect(R.transitions).toEqual([]);
    expect(screen.getByTestId("gate-home")).toHaveAttribute("href", "/");
    expect(screen.getByTestId("shell-back")).toBeInTheDocument(); // and Wapas is there too
  }, 15_000);
});

describe("Simple ⇄ Pro switching never dead-ends", () => {
  it("a Pro account toggling Simple in Settings LANDS on the Simple home, levelled by its real state, with visible locks", async () => {
    server.createdAt = "2026-03-01T00:00:00Z"; // existing → Pro
    server.brokerConnected = true;
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("pro-home")).toBeInTheDocument());
    act(() => push("/settings"));
    await waitFor(() => expect(screen.getByTestId("mode-card")).toBeInTheDocument());
    R.transitions = [];
    fireEvent.click(screen.getByTestId("mode-simple"));
    await waitFor(() => expect(screen.getByTestId("simple-home")).toBeInTheDocument());
    await settle();
    expect(R.transitions).toEqual(["push:/"]);
    expect(screen.queryByTestId("pro-sidebar")).toBeNull();
    // Real state: broker connected → the Templates lock names ONLY the two missing steps
    await waitFor(() => expect(screen.getByTestId("locked-hint-templates")).toHaveTextContent("Strategy chuno + pehla signal dekho, phir yeh khulega"));
    expect(screen.getByTestId("locked-pro")).toBeInTheDocument();
    expect(screen.getByTestId("pro-entry")).toBeInTheDocument();
    expect(screen.getByTestId("progress-line")).toHaveTextContent("1 / 4");
  }, 15_000);

  it("toggling Pro in Settings lands on the Pro dashboard immediately, sidebar expanded once, nudge shown", async () => {
    server.createdAt = "2026-09-06T08:00:00Z"; // a new customer who wants everything now
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
    // …and NOT the 5-step tour modal on top of it (it covered the page on the walk).
    expect(screen.queryByTestId("pro-tour")).toBeNull();
  }, 15_000);

  it("an existing Pro account still gets its welcome tour (unchanged)", async () => {
    server.createdAt = "2026-03-01T00:00:00Z";
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("pro-home")).toBeInTheDocument());
    expect(screen.getByTestId("pro-tour")).toBeInTheDocument();
  }, 15_000);

  it("the Pro entry card on the home is one tap into Pro", async () => {
    render(<Providers><App /></Providers>);
    await waitFor(() => expect(screen.getByTestId("pro-entry")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("pro-entry"));
    await waitFor(() => expect(screen.getByTestId("pro-home")).toBeInTheDocument());
    expect(screen.getByTestId("pro-welcome-nudge")).toBeInTheDocument();
  }, 15_000);
});
