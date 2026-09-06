/**
 * The paper-mode strip, on every surface where a customer can ACT.
 *
 * The component existed and was imported by NOTHING — the "orders are
 * simulated" disclosure rendered on no page at all. These tests pin the
 * mount points (signals, My Strategies, positions, the Deploy panel) and
 * the three server states:
 *
 *   paper_mode === true   → the strip renders, saying simulated
 *   paper_mode === false  → nothing renders
 *   unknown (hook null)   → nothing renders. Not "simulated", not "real".
 *                           We have not read the flag, so we claim neither.
 *
 * The banner is driven ONLY through ``useSystemMode`` — mocking that hook
 * is enough to move all four surfaces, which is the proof there is one
 * owner of the fact and not a second copy of the fetch inside the banner.
 */

import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

// ── Mocks ────────────────────────────────────────────────────────────

beforeAll(() => {
  if (!("IntersectionObserver" in globalThis)) {
    class IO {
      observe() {} unobserve() {} disconnect() {}
      takeRecords() { return []; }
      root = null; rootMargin = ""; thresholds = [];
    }
    (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver = IO;
  }
});

type Mode = {
  paper_mode: boolean;
  kill_switch_check_enabled: boolean;
  circuit_breaker_enabled: boolean;
};

/** The ONE source of the paper fact. ``null`` = unknown (loading or failed). */
const systemMode = vi.hoisted(() => ({ current: null as Mode | null }));
vi.mock("@/hooks/useSystemMode", () => ({
  useSystemMode: () => systemMode.current,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/signals",
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "t@x.com", role: "user" } }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));
vi.mock("@/shared/api/client", () => {
  class ApiError extends Error {
    status: number;
    detail: string;
    data?: unknown;
    constructor(status: number, detail: string, data?: unknown) {
      super(detail);
      this.status = status;
      this.detail = detail;
      this.data = data;
    }
  }
  return { api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }, ApiError };
});

// Every surface's data source. Nothing loaded — the banner must not depend
// on a page having data.
vi.mock("@/shared/api/use-api", () => ({
  useApi: () => ({
    data: null,
    isLoading: false,
    error: null,
    paywalled: false,
    paywallUrl: null,
    refetch: vi.fn(),
  }),
}));

import { PaperModeBanner } from "@/components/dashboard/paper-mode-banner";
import { StepDeploy } from "@/components/strategies/beginner-builder/step-deploy";
import SignalsPage from "@/app/(dashboard)/signals/page";
import MyStrategiesPage from "@/app/(dashboard)/marketplace/me/page";
import PositionsPage from "@/app/(dashboard)/positions/page";

const PAPER: Mode = {
  paper_mode: true,
  kill_switch_check_enabled: true,
  circuit_breaker_enabled: true,
};
const REAL: Mode = { ...PAPER, paper_mode: false };

/** The four surfaces a customer can act from. */
const SURFACES: { name: string; render: () => void }[] = [
  { name: "Signals (confirm a signal)", render: () => { render(<SignalsPage />); } },
  { name: "My Strategies (deploy / pause)", render: () => { render(<MyStrategiesPage />); } },
  { name: "Positions (close a position)", render: () => { render(<PositionsPage />); } },
  {
    name: "Deploy panel (go live)",
    render: () => {
      render(
        <StepDeploy strategyId="s-1" strategyName="Test strategy" onBack={() => {}} />,
      );
    },
  },
];

beforeEach(() => {
  systemMode.current = null;
});
afterEach(() => {
  cleanup();
});

// ── Server says PAPER ────────────────────────────────────────────────

describe("server says paper_mode=true", () => {
  for (const surface of SURFACES) {
    it(`🔴 discloses simulated orders on ${surface.name}`, () => {
      systemMode.current = PAPER;
      surface.render();

      const banner = screen.getByTestId("paper-mode-banner");
      expect(banner).toBeInTheDocument();
      expect(banner.textContent ?? "").toMatch(/paper mode/i);
      expect(banner.textContent ?? "").toMatch(/simulate/i);
      // Announced, not just painted.
      expect(banner).toHaveAttribute("role", "status");
    });
  }
});

// ── Server says REAL ─────────────────────────────────────────────────

describe("server says paper_mode=false", () => {
  for (const surface of SURFACES) {
    it(`🔴 says nothing about simulated orders on ${surface.name}`, () => {
      systemMode.current = REAL;
      surface.render();

      expect(screen.queryByTestId("paper-mode-banner")).toBeNull();
      for (const status of screen.queryAllByRole("status")) {
        expect(status.textContent ?? "").not.toMatch(/paper mode/i);
      }
    });
  }
});

// ── Server state UNKNOWN ─────────────────────────────────────────────

describe("server state unknown (first poll in flight, or every poll failed)", () => {
  for (const surface of SURFACES) {
    it(`🔴 claims neither simulated nor real on ${surface.name}`, () => {
      systemMode.current = null; // the hook's "we have not read it" value
      surface.render();

      // Not "simulated".
      expect(screen.queryByTestId("paper-mode-banner")).toBeNull();
      // And not "real money" either — the banner asserts nothing at all.
      for (const status of screen.queryAllByRole("status")) {
        const text = status.textContent ?? "";
        expect(text).not.toMatch(/paper mode/i);
        expect(text).not.toMatch(/real money|live trading on|asli paisa/i);
      }
    });
  }
});

// ── One owner of the fact ────────────────────────────────────────────

describe("one owner of the paper fact", () => {
  it("🔴 reads the flag through useSystemMode, not its own fetch", () => {
    const fetchSpy = vi.fn();
    const original = globalThis.fetch;
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
    try {
      systemMode.current = PAPER;
      render(<PaperModeBanner />);
      // Rendered from the hook alone.
      expect(screen.getByTestId("paper-mode-banner")).toBeInTheDocument();
      // The banner used to duplicate useSystemMode's fetch/BASE/parse.
      expect(fetchSpy).not.toHaveBeenCalled();
    } finally {
      globalThis.fetch = original;
    }
  });

  it("flips with the server value, with no other input changing", () => {
    systemMode.current = PAPER;
    const { rerender } = render(<PaperModeBanner />);
    expect(screen.queryByTestId("paper-mode-banner")).not.toBeNull();

    systemMode.current = REAL;
    rerender(<PaperModeBanner />);
    expect(screen.queryByTestId("paper-mode-banner")).toBeNull();
  });
});
