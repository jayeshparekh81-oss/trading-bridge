/**
 * "Paper mode" may only be claimed where paper is TRUE.
 *
 * THE DEFECT THESE TESTS EXIST FOR (2026-09-09, founder's own account)
 * ────────────────────────────────────────────────────────────────────
 * `PaperModeBanner` derived its truth from ONE global platform flag
 * (`GET /api/system/mode` → `paper_mode`) and was mounted on /positions,
 * which renders the OWNER's REAL-MONEY rows. It told him
 * "broker ko koi asli order nahi jaata" while Dhan held a live BSE futures
 * position bought with real money.
 *
 * The global flag was not merely the wrong scope — it contradicts the
 * backend's own rule. `app/services/paper_mode_resolver.py` resolves
 * paper-ness as `strategy.is_paper if not None else settings.paper_mode`:
 * the PER-STRATEGY flag wins, and production rows always carry one, so the
 * global flag decides nothing in production. The UI was reading a value the
 * executor ignores.
 *
 * The rule now pinned here:
 *   every row paper  → the blanket banner is true, show it
 *   mixed            → NO blanket claim; per-row labels carry the truth
 *   nothing paper    → nothing to disclose
 *   any row unknown  → claim NOTHING. Not simulated, not real.
 *
 * The previous version of this file asserted the opposite — that a global
 * `paper_mode=true` puts the "simulated" strip on all four acting surfaces
 * regardless of what those surfaces show. That assertion IS the bug, so it
 * is gone rather than adapted.
 */

import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

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

const systemMode = vi.hoisted(() => ({ current: null as Mode | null }));
vi.mock("@/hooks/useSystemMode", () => ({
  useSystemMode: () => systemMode.current,
}));

/** Per-URL API responses, so a page's own rows drive its disclosure. */
const apiData = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));
vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => {
    // "/strategies" must be matched before the "/strategies/positions" prefix.
    const key =
      url === null
        ? "__null__"
        : Object.keys(apiData.current)
            .sort((a, b) => b.length - a.length)
            .find((k) => url === k || url.startsWith(k)) ?? "__miss__";
    return {
      data: apiData.current[key] ?? null,
      isLoading: false,
      error: null,
      paywalled: false,
      paywallUrl: null,
      refetch: vi.fn(),
    };
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/positions",
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "t@x.com", role: "user" } }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));
vi.mock("@/shared/api/client", () => {
  class ApiError extends Error {
    status: number; detail: string; data?: unknown;
    constructor(status: number, detail: string, data?: unknown) {
      super(detail); this.status = status; this.detail = detail; this.data = data;
    }
  }
  return { api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() }, ApiError };
});

import { PaperModeBanner, PaperRowBadge } from "@/components/dashboard/paper-mode-banner";
import {
  paperScope,
  resolvePaperMode,
  subscriptionPaperMode,
} from "@/lib/paper-mode";
import PositionsPage from "@/app/(dashboard)/positions/page";

const PAPER: Mode = {
  paper_mode: true,
  kill_switch_check_enabled: true,
  circuit_breaker_enabled: true,
};
const REAL: Mode = { ...PAPER, paper_mode: false };

const LIVE_STRATEGY = "89423ecc-c76e-432c-b107-0791508542f0";
const PAPER_STRATEGY = "0fa00000-0000-0000-0000-000000000001";

/** The founder's real row: BSE LTD Futures, is_paper = FALSE. */
function livePosition(over: Record<string, unknown> = {}) {
  return {
    id: "d0086394-e66b-4b49-b557-7c337df777ac",
    strategy_id: LIVE_STRATEGY,
    symbol: "BSE-SEP2026-FUT",
    side: "sell",
    total_quantity: 400,
    remaining_quantity: 200,
    avg_entry_price: "3393.1500",
    target_price: null,
    stop_loss_price: null,
    highest_price_seen: null,
    status: "partial",
    opened_at: "2026-09-08T08:30:11Z",
    closed_at: null,
    final_pnl: null,
    ...over,
  };
}

/** The throwaway paper row that shares the page with it in production. */
function paperPosition(over: Record<string, unknown> = {}) {
  return {
    ...livePosition(),
    id: "f6b58ffc-62d8-4514-8875-9b93138f3d9c",
    strategy_id: PAPER_STRATEGY,
    symbol: "BSE-AUG2026-FUT",
    side: "buy",
    status: "closed",
    ...over,
  };
}

const STRATEGIES = {
  strategies: [
    { id: LIVE_STRATEGY, name: "BSE LTD Futures", is_paper: false },
    { id: PAPER_STRATEGY, name: "PAPER FANOUT TEST — delete me", is_paper: true },
  ],
  count: 2,
};

beforeEach(() => {
  systemMode.current = null;
  apiData.current = {};
});
afterEach(() => {
  cleanup();
});

// ── The regression itself ────────────────────────────────────────────

describe("/positions never calls real money simulated", () => {
  it("🔴 shows NO simulated-orders banner over live rows, even with the platform flag ON", () => {
    // The exact production shape on 2026-09-09: a live-money row, and a
    // platform flag that used to be the banner's only input.
    systemMode.current = PAPER;
    apiData.current = {
      "/strategies": STRATEGIES,
      "/strategies/positions": { positions: [livePosition()], count: 1 },
    };

    render(<PositionsPage />);

    expect(screen.queryByTestId("paper-mode-banner")).toBeNull();
    for (const status of screen.queryAllByRole("status")) {
      expect(status.textContent ?? "").not.toMatch(/asli order nahi jaata/i);
    }
  });

  it("🔴 labels the live row LIVE, not Paper", () => {
    systemMode.current = PAPER;
    apiData.current = {
      "/strategies": STRATEGIES,
      "/strategies/positions": { positions: [livePosition()], count: 1 },
    };

    render(<PositionsPage />);

    expect(screen.getByTestId("row-mode-live")).toBeInTheDocument();
    expect(screen.queryByTestId("row-mode-paper")).toBeNull();
  });

  it("🔴 a MIXED page makes no blanket claim, and labels every row", () => {
    // Production really does mix: the live BSE rows sit beside the paper
    // fan-out test row, so no single sentence about this page can be true.
    systemMode.current = REAL;
    apiData.current = {
      "/strategies": STRATEGIES,
      "/strategies/positions": {
        positions: [livePosition(), paperPosition()],
        count: 2,
      },
    };

    render(<PositionsPage />);

    // No blanket "everything here is simulated".
    expect(screen.queryByTestId("paper-mode-banner")).toBeNull();
    // The mixed notice points at the per-row truth instead of averaging it.
    const mixed = screen.getByTestId("paper-mode-banner-mixed");
    expect(mixed.textContent ?? "").not.toMatch(/asli order nahi jaata/i);
    // One label per row, and they disagree — which is the whole point.
    expect(screen.getByTestId("row-mode-live")).toBeInTheDocument();
    expect(screen.getByTestId("row-mode-paper")).toBeInTheDocument();
  });

  it("🔴 says nothing at all when the strategy list has not loaded", () => {
    // A failed/pending join must never fall back to the global flag — that
    // fallback is precisely how real money got called simulated.
    systemMode.current = PAPER;
    apiData.current = {
      "/strategies/positions": { positions: [livePosition()], count: 1 },
      // "/strategies" deliberately absent → unknown
    };

    render(<PositionsPage />);

    expect(screen.queryByTestId("paper-mode-banner")).toBeNull();
    expect(screen.queryByTestId("paper-mode-banner-mixed")).toBeNull();
    expect(screen.queryByTestId("row-mode-live")).toBeNull();
    expect(screen.queryByTestId("row-mode-paper")).toBeNull();
  });

  it("discloses simulated orders when EVERY row really is paper", () => {
    systemMode.current = REAL; // platform says real; the rows still say paper
    apiData.current = {
      "/strategies": STRATEGIES,
      "/strategies/positions": { positions: [paperPosition()], count: 1 },
    };

    render(<PositionsPage />);

    const banner = screen.getByTestId("paper-mode-banner");
    expect(banner.textContent ?? "").toMatch(/simulate/i);
    expect(banner).toHaveAttribute("role", "status");
  });
});

// ── The price sentinel ───────────────────────────────────────────────

describe("a missing price is never rendered as ₹0", () => {
  it("🔴 renders — for the Decimal('0') sentinel arriving as the string 0.0000", () => {
    // `"0.0000"` is a non-empty string and therefore TRUTHY: the old
    // `p.avg_entry_price ? … : "—"` guard never fired and printed ₹0.
    systemMode.current = REAL;
    apiData.current = {
      "/strategies": STRATEGIES,
      "/strategies/positions": {
        positions: [paperPosition({ avg_entry_price: "0.0000" })],
        count: 1,
      },
    };

    render(<PositionsPage />);

    const row = screen.getByText("BSE-AUG2026-FUT").closest("tr")!;
    expect(within(row).queryByText("₹0")).toBeNull();
    expect(within(row).getAllByText("—").length).toBeGreaterThan(0);
  });

  it("a real breakeven P&L of exactly zero still renders ₹0", () => {
    // Only PRICES use zero as "unknown". A zero P&L is a fact.
    systemMode.current = REAL;
    apiData.current = {
      "/strategies": STRATEGIES,
      "/strategies/positions": {
        positions: [paperPosition({ final_pnl: "0.00" })],
        count: 1,
      },
    };

    render(<PositionsPage />);

    const row = screen.getByText("BSE-AUG2026-FUT").closest("tr")!;
    expect(within(row).getByText("₹0")).toBeInTheDocument();
  });
});

// ── The resolution rule, mirrored from the backend ───────────────────

describe("resolvePaperMode mirrors app/services/paper_mode_resolver.py", () => {
  it("the per-strategy flag WINS over the global flag, both ways", () => {
    expect(resolvePaperMode(false, true)).toBe(false); // live strategy, paper platform
    expect(resolvePaperMode(true, false)).toBe(true);  // paper strategy, live platform
  });

  it("the global flag is used ONLY when the strategy carries no value", () => {
    expect(resolvePaperMode(null, true)).toBe(true);
    expect(resolvePaperMode(undefined, false)).toBe(false);
  });

  it("unknown on both sides stays unknown — never a default", () => {
    expect(resolvePaperMode(null, null)).toBeNull();
    expect(resolvePaperMode(undefined, undefined)).toBeNull();
  });
});

describe("paperScope reduces a surface to the strongest TRUE claim", () => {
  it("all paper → all-paper; none → none-paper; both → mixed", () => {
    expect(paperScope([true, true])).toBe("all-paper");
    expect(paperScope([false, false])).toBe("none-paper");
    expect(paperScope([true, false])).toBe("mixed");
  });

  it("🔴 one unread row poisons the blanket claim", () => {
    // A banner speaks for rows it cannot see, so unknown is contagious.
    expect(paperScope([true, null])).toBe("unknown");
    expect(paperScope([false, undefined])).toBe("unknown");
  });

  it("🔴 an EMPTY surface is not vacuously all-paper", () => {
    // "every one of zero rows is simulated" is true and useless — it would
    // print a paper banner over an empty table.
    expect(paperScope([])).toBe("none-paper");
  });
});

describe("subscriptionPaperMode reads only what the server said", () => {
  it("prefers the subscription's own flag", () => {
    expect(subscriptionPaperMode({ is_paper: false, execution_mode: "paper" })).toBe(false);
  });

  it('treats execution_mode "paper" as proof of paper', () => {
    expect(subscriptionPaperMode({ execution_mode: "paper" })).toBe(true);
  });

  it('🔴 does NOT read "auto" as proof of real money', () => {
    // "auto" still executes as paper until Phase 3 / empanelment, so it
    // proves nothing either way.
    expect(subscriptionPaperMode({ execution_mode: "auto" })).toBeNull();
  });

  it("falls back to the open position's own fill mode", () => {
    expect(subscriptionPaperMode({ open_position: { paper_mode: true } })).toBe(true);
  });

  it("says nothing when the server said nothing", () => {
    expect(subscriptionPaperMode({})).toBeNull();
    expect(subscriptionPaperMode(null)).toBeNull();
  });
});

// ── The component contract ───────────────────────────────────────────

describe("PaperModeBanner renders only what its scope permits", () => {
  it("🔴 renders nothing for unknown and for none-paper", () => {
    const { container: a } = render(<PaperModeBanner scope="unknown" />);
    expect(a).toBeEmptyDOMElement();
    cleanup();
    const { container: b } = render(<PaperModeBanner scope="none-paper" />);
    expect(b).toBeEmptyDOMElement();
  });

  it("🔴 has no fetch of its own — the scope is handed in", () => {
    const fetchSpy = vi.fn();
    const original = globalThis.fetch;
    globalThis.fetch = fetchSpy as unknown as typeof fetch;
    try {
      render(<PaperModeBanner scope="all-paper" />);
      expect(screen.getByTestId("paper-mode-banner")).toBeInTheDocument();
      expect(fetchSpy).not.toHaveBeenCalled();
    } finally {
      globalThis.fetch = original;
    }
  });
});

describe("PaperRowBadge", () => {
  it("🔴 renders NOTHING for an unknown row — never a guess", () => {
    const { container } = render(<PaperRowBadge paper={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("names live and paper distinctly", () => {
    render(<PaperRowBadge paper={false} />);
    expect(screen.getByTestId("row-mode-live").textContent ?? "").toMatch(/live/i);
    cleanup();
    render(<PaperRowBadge paper={true} />);
    expect(screen.getByTestId("row-mode-paper").textContent ?? "").toMatch(/paper/i);
  });
});
