/**
 * THE LOOP + "a practice account never needs a Dhan token" (founder walked the live site as the
 * test customer, 2 Oct 2026): the guided path threw him back to "Dhan jodo" again and again — after
 * moving forward, and even after reaching the Simple Mode home.
 *
 * Root cause (file:line): backend guided_path.done("BROKER") = `broker_state == "ACTIVE"` alone →
 * first_incomplete/resume_step = BROKER for every customer without a Dhan token; the dashboard
 * layout ((dashboard)/layout.tsx firstRun → /start) then re-opened the guide on every visit; and
 * "Baad me karunga" changed nothing on the server or on the device.
 *
 * Frontend half pinned here: (1) BROKER's one primary is "Bina Dhan ke aage badho (practice)" and
 * it tells the server {later: true}; the token form is a quiet second button; (2) leaving the guide
 * is remembered and the dashboard never bounces a customer who left; opening /start clears it;
 * (3) steps that do not apply are hidden, not struck out; (4) the /start banner is not sticky;
 * (5) Hinglish is the default language.
 */
// 2 Oct 2026: default is ENGLISH; this file pins HINGLISH words, so it describes an account that CHOSE Hinglish.
import "../i18n/hinglish-account";
import { forceLang } from "../i18n/force-lang";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const STATES = JSON.parse(readFileSync(join(process.cwd(), "tests/guided/fixtures/states.json"), "utf8"));

const guidedApi = vi.hoisted(() => ({
  publicStart: vi.fn(), state: vi.fn(), choose: vi.fn(), back: vi.fn(), broker: vi.fn(), ask: vi.fn(),
  confirm: vi.fn(), running: vi.fn(), stopPreview: vi.fn(), stop: vi.fn(), signup: vi.fn(), restart: vi.fn(),
}));
vi.mock("@/lib/guided-path", async (orig) => {
  const real = await orig<typeof import("@/lib/guided-path")>();
  return { ...real, guidedApi, guidedPathLive: vi.fn(async () => true) };
});
const nav = vi.hoisted(() => ({ replace: vi.fn(), push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: nav.replace, push: nav.push, refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));
// the dashboard layout's chrome is not under test
const auth = { user: { id: "u1", email: "c@x.com", full_name: "C", is_admin: false, onboarding_step: 2 } as Record<string, unknown>, isLoading: false, isAuthenticated: true };
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ ...auth, logout: vi.fn() }),
  useAuthOptional: () => ({ ...auth, logout: vi.fn(), refreshUser: vi.fn(async () => undefined) }),
}));
vi.mock("@/hooks/useLadder", () => ({ useLadder: () => ({ ready: true, level: 4, choice: "pro" }) }));
vi.mock("@/hooks/useGuidedPathLive", () => ({ useGuidedPathLive: () => "ready" }));
vi.mock("@/hooks/use-algomitra-context", () => ({ useAlgoMitraPanelState: () => ({ isOpen: false }) }));
vi.mock("@/components/dashboard/sidebar", () => ({ Sidebar: () => null }));
vi.mock("@/components/dashboard/top-bar", () => ({ TopBar: () => null }));
vi.mock("@/components/dashboard/mobile-nav", () => ({ MobileNav: () => null }));
vi.mock("@/components/algomitra/ChatWidget", () => ({ ChatWidget: () => null }));
vi.mock("@/components/algomitra/AlgoMitraReactionLayer", () => ({ AlgoMitraReactionLayer: () => null }));
vi.mock("@/components/algomitra/always-on-panel", () => ({ AlwaysOnAlgoMitraPanelMount: () => null }));
vi.mock("@/components/onboarding/OnboardingTour", () => ({ OnboardingTour: () => null }));
vi.mock("@/components/privacy-banner", () => ({ PrivacyBanner: () => null }));
vi.mock("@/components/simple/pro-welcome-nudge", () => ({ ProWelcomeNudge: () => null }));
vi.mock("@/components/simple/simple-shell", () => ({ SimpleShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("@/shared/ui/skeleton-loader", () => ({ DashboardSkeleton: () => <div data-testid="skeleton" /> }));

import * as lib from "@/lib/guided-path";
import { GuidedPath } from "@/components/guided/guided-path";
import { ProgressBar } from "@/components/guided/guided-parts";
import DashboardLayout from "@/app/(dashboard)/layout";
import StartLayout from "@/app/start/layout";

const BROKER_STATE = { ...STATES.BROKER, screen: { ...STATES.BROKER.screen, broker_state: "NONE" } };

beforeEach(() => {
  Object.values(guidedApi).forEach((f) => f.mockReset());
  nav.replace.mockReset();
  localStorage.clear();
  forceLang("hinglish");
  localStorage.setItem("tb_access_token", "t");
  auth.user = { id: "u1", email: "c@x.com", full_name: "C", is_admin: false, onboarding_step: 2 };
});
afterEach(() => localStorage.clear());

describe("1. the BROKER step on a practice account", () => {
  it("the ONE primary skips Dhan and tells the server {later: true}; the token form is a quiet second button", async () => {
    guidedApi.state.mockResolvedValue(BROKER_STATE);
    guidedApi.choose.mockResolvedValue(STATES.STRATEGY);
    render(<GuidedPath />);
    await screen.findByTestId("screen-BROKER");
    expect(screen.getByTestId("broker-practice-line").textContent).toMatch(/zaroori nahi/);
    const next = screen.getByTestId("guided-next");
    expect(next.textContent).toMatch(/Bina Dhan ke aage badho/);
    expect(next.getAttribute("data-primary")).toBe("true");
    expect((next as HTMLButtonElement).disabled).toBe(false);          // no token typed, still goes
    expect(document.querySelectorAll('[data-primary="true"]').length).toBe(1);
    const connect = screen.getByTestId("broker-connect") as HTMLButtonElement;
    expect(connect.getAttribute("data-primary")).toBeNull();
    expect(connect.disabled).toBe(true);                                // nothing typed yet
    fireEvent.click(next);
    await waitFor(() => expect(guidedApi.choose).toHaveBeenCalledWith("BROKER", { later: true }));
    expect(guidedApi.broker).not.toHaveBeenCalled();
  });

  it("typing both fields enables the quiet connect button, which calls /broker (not the skip)", async () => {
    guidedApi.state.mockResolvedValue(BROKER_STATE);
    guidedApi.broker.mockResolvedValue(STATES.STRATEGY);
    render(<GuidedPath />);
    await screen.findByTestId("screen-BROKER");
    const inputs = screen.getByTestId("broker-connect-now").querySelectorAll("input, textarea");
    fireEvent.change(inputs[0], { target: { value: "1100000001" } });
    fireEvent.change(inputs[1], { target: { value: "GOOD" + "g".repeat(120) } });
    const connect = screen.getByTestId("broker-connect") as HTMLButtonElement;
    expect(connect.disabled).toBe(false);
    fireEvent.click(connect);
    await waitFor(() => expect(guidedApi.broker).toHaveBeenCalledWith("1100000001", "GOOD" + "g".repeat(120)));
    expect(guidedApi.choose).not.toHaveBeenCalled();
  });
});

describe("2. THE LOOP — leaving the guide is remembered; the dashboard does not bounce", () => {
  it("'Baad me karunga' marks the device; the dashboard then renders instead of replacing to /start", async () => {
    // the exit link lives on the first logged-in screen (BROKER has nothing behind it); later
    // screens offer Back — a customer who simply leaves the tab resumes at the right step
    guidedApi.state.mockResolvedValue(BROKER_STATE);
    render(<GuidedPath />);
    await screen.findByTestId("screen-BROKER");
    const leave = screen.getByTestId("guided-back");
    expect(leave.textContent).toMatch(/Baad me karunga/);
    fireEvent.click(leave);
    expect(lib.guidedLeft()).toBe(true);
    const r = render(<DashboardLayout><p data-testid="page">Ghar</p></DashboardLayout>);
    await waitFor(() => expect(screen.getByTestId("page")).toBeInTheDocument());
    expect(nav.replace).not.toHaveBeenCalledWith("/start");
    r.unmount();
  });

  it("🔴 without the flag the layout still sends a first-run customer to /start (the one path), and opening the guide clears the flag", async () => {
    lib.markGuidedLeft();
    guidedApi.state.mockResolvedValue(STATES.STRATEGY);
    const g = render(<GuidedPath />);
    await screen.findByTestId("screen-STRATEGY");
    g.unmount();
    expect(lib.guidedLeft()).toBe(false);                               // came back → cleared
    render(<DashboardLayout><p data-testid="page2">x</p></DashboardLayout>);
    await waitFor(() => expect(nav.replace).toHaveBeenCalledWith("/start"));
  });

  it("the layout reads the device flag through lib/guided-path (source)", () => {
    const src = readFileSync(resolve(__dirname, "../../src/app/(dashboard)/layout.tsx"), "utf8");
    expect(src).toMatch(/if \(guidedLeft\(\)\) return;\s*\n\s*router\.replace\("\/start"\)/);
  });
});

describe("3. steps that do not apply are hidden, not struck out", () => {
  it("the bar lists only counted steps and counts them", () => {
    const items = [
      { n: 1, step: "BROKER", title: "Dhan jodo", state: "NOT_NEEDED" },
      { n: 2, step: "STRATEGY", title: "Strategy chuno", state: "DONE" },
      { n: 3, step: "VEHICLE", title: "Kis cheez me trade", state: "NOT_NEEDED" },
      { n: 4, step: "STRIKE", title: "Strike ki doori", state: "NOT_NEEDED" },
      { n: 5, step: "SIZE", title: "Size aur risk", state: "CURRENT" },
      { n: 6, step: "CONFIRM", title: "Pakka karo", state: "TODO" },
    ] as const;
    render(<ProgressBar items={[...items]} />);
    expect(screen.getByTestId("guided-progress-count").textContent).toBe("Kadam 2 / 3");
    expect(screen.queryByText(/lagu nahi/)).toBeNull();
    expect(screen.queryByTestId("guided-bar-VEHICLE")).toBeNull();
    expect(screen.queryByTestId("guided-bar-STRIKE")).toBeNull();
    expect(screen.queryByTestId("guided-bar-BROKER")).toBeNull();
    expect(document.querySelectorAll(".line-through").length).toBe(0);
    expect(screen.getByTestId("guided-bar-SIZE")).toBeInTheDocument();
  });
});

describe("4. the /start banner never covers the stepper", () => {
  it("is on the screen but not sticky", () => {
    render(<StartLayout><p>screen</p></StartLayout>);
    const b = screen.getByTestId("practice-banner");
    expect(b.className).not.toMatch(/\bsticky\b/);
  });
});

describe("5. English is the default language (founder, 2 Oct 2026 — reversed the morning's Hinglish default)", () => {
  it("the provider's default is English, there is no navigator guess, and Hinglish is the first alternative on the switch (source)", async () => {
    const src = readFileSync(resolve(__dirname, "../../src/contexts/LanguageContext.tsx"), "utf8");
    expect(src).toMatch(/const DEFAULT_LANG: Lang = "en";/);
    expect(src).not.toMatch(/navigator\.language/);
    const sync = await import("@/lib/simple/language-sync");
    expect(sync.SIMPLE_LANGS.map((l) => l.code)).toEqual(["en", "hinglish", "hi", "gu"]);
  });
});
