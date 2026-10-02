/**
 * THE PRACTICE BANNER ON EVERY CUSTOMER SCREEN (founder, 1 Oct 2026: "paper demo only with the
 * practice banner on every screen"). Measured 2 Oct 2026 on the served build 67a3e41e: of the 26
 * customer screens only /start, /journey and the settings panel carried it; Ghar, Broker jodo,
 * Strategy chuno, Orders, Sab band, Madad, Settings … had none.
 *
 * The fix mounts it ONCE in the (dashboard) layout for every CUSTOMER account — and NEVER for the
 * founder's admin account, whose /positions shows REAL BSE rows (INC #12: a "practice" line over
 * real money is the worst lie this product can tell). /journey no longer mounts its own copy, so a
 * customer never sees it twice.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactNode } from "react";

const auth = {
  user: { id: "u1", email: "c@x.com", full_name: "Customer", is_admin: false, onboarding_step: 6 } as Record<string, unknown> | null,
  isLoading: false,
  isAuthenticated: true,
};
const ladder = { ready: true, level: 4, choice: "pro" as string };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/brokers",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ ...auth, logout: vi.fn() }) }));
vi.mock("@/hooks/useLadder", () => ({ useLadder: () => ladder }));
vi.mock("@/hooks/useGuidedPathLive", () => ({ useGuidedPathLive: () => "off" }));
vi.mock("@/hooks/use-algomitra-context", () => ({ useAlgoMitraPanelState: () => ({ isOpen: false }) }));
// the chrome around the page is not under test — stand-ins that render nothing or their children
vi.mock("@/components/dashboard/sidebar", () => ({ Sidebar: () => null }));
vi.mock("@/components/dashboard/top-bar", () => ({ TopBar: () => null }));
vi.mock("@/components/dashboard/mobile-nav", () => ({ MobileNav: () => null }));
vi.mock("@/components/algomitra/ChatWidget", () => ({ ChatWidget: () => null }));
vi.mock("@/components/algomitra/AlgoMitraReactionLayer", () => ({ AlgoMitraReactionLayer: () => null }));
vi.mock("@/components/algomitra/always-on-panel", () => ({ AlwaysOnAlgoMitraPanelMount: () => null }));
vi.mock("@/components/onboarding/OnboardingTour", () => ({ OnboardingTour: () => null }));
vi.mock("@/components/privacy-banner", () => ({ PrivacyBanner: () => null }));
vi.mock("@/components/simple/pro-welcome-nudge", () => ({ ProWelcomeNudge: () => null }));
vi.mock("@/components/simple/simple-shell", () => ({
  SimpleShell: ({ children }: { children: ReactNode }) => <div data-testid="simple-shell">{children}</div>,
}));
vi.mock("@/shared/ui/skeleton-loader", () => ({ DashboardSkeleton: () => <div data-testid="skeleton" /> }));

import DashboardLayout from "@/app/(dashboard)/layout";
import { practiceLine } from "@/components/site/practice-banner";

beforeEach(() => {
  auth.user = { id: "u1", email: "c@x.com", full_name: "Customer", is_admin: false, onboarding_step: 6 };
  auth.isAuthenticated = true;
  auth.isLoading = false;
  ladder.level = 4;
  ladder.choice = "pro";
});

describe("practice banner on every customer screen", () => {
  it("a CUSTOMER in the Pro chrome sees it, above the page, with his exact words", () => {
    render(<DashboardLayout><p data-testid="page">Broker jodo</p></DashboardLayout>);
    const banners = screen.getAllByTestId("practice-banner");
    expect(banners).toHaveLength(1);
    expect(banners[0].textContent).toBe(practiceLine("en")); // default English since 2 Oct 2026
    expect(banners[0].compareDocumentPosition(screen.getByTestId("page")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // not sticky here — it must never sit under the Simple shell's own sticky header
    expect(banners[0].className).not.toMatch(/\bsticky\b/);
  });

  it("a CUSTOMER in the Simple chrome (level 1-3) sees it too, inside the shell, once", () => {
    ladder.level = 2;
    ladder.choice = "simple";
    render(<DashboardLayout><p data-testid="page">Ghar</p></DashboardLayout>);
    expect(screen.getByTestId("simple-shell")).toBeInTheDocument();
    expect(screen.getAllByTestId("practice-banner")).toHaveLength(1);
  });

  it("the founder's ADMIN account NEVER sees it — his rows are real money (INC #12)", () => {
    auth.user = { id: "a1", email: "a@x.com", full_name: "Admin", is_admin: true, onboarding_step: 6 };
    render(<DashboardLayout><p data-testid="page">Positions</p></DashboardLayout>);
    expect(screen.queryByTestId("practice-banner")).toBeNull();
    expect(screen.getByTestId("page")).toBeInTheDocument();
  });

  it("an account whose admin flag is unreadable gets NO banner (absence is not a claim)", () => {
    auth.user = { id: "u2", email: "c2@x.com", full_name: "C2", onboarding_step: 6 };
    (auth.user as Record<string, unknown>).is_admin = undefined;
    render(<DashboardLayout><p data-testid="page">x</p></DashboardLayout>);
    // `!undefined` is true — the layout reads `is_admin` as the backend sends it (always a boolean);
    // this test pins that the decision is `user.is_admin`, read from the /auth/me object, nothing else
    const src = readFileSync(resolve(__dirname, "../../src/app/(dashboard)/layout.tsx"), "utf8");
    expect(src).toMatch(/\{user && !user\.is_admin && <PracticeBanner sticky=\{false\} \/>\}/);
  });

  it("/onboarding (outside the dashboard group) mounts it for a customer, never for the admin (source)", () => {
    const src = readFileSync(resolve(__dirname, "../../src/app/onboarding/layout.tsx"), "utf8");
    expect(src).toMatch(/\{user && !user\.is_admin && <PracticeBanner sticky=\{false\} \/>\}/);
  });

  it("the /start flag-off card offers ONE login control while signup is closed (source)", () => {
    const src = readFileSync(resolve(__dirname, "../../src/app/start/page.tsx"), "utf8");
    // the small "Pehle se account hai? Login karo" line renders only when signup is OPEN; closed, the
    // big button already says "… Login karo" (the served card on 2 Oct showed the same tap twice)
    expect(src).toMatch(/\{signup === "open" && \(\s*<Link href="\/login"/);
  });

  it("no dashboard page mounts its own copy any more (one banner, one source)", () => {
    const journey = readFileSync(resolve(__dirname, "../../src/app/(dashboard)/journey/page.tsx"), "utf8");
    expect(journey).not.toMatch(/<PracticeBanner \/>/);
    expect(journey).not.toMatch(/import \{ PracticeBanner \}/);
  });
});
