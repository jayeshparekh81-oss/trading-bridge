/**
 * An invisible stop reads as no stop.
 *
 * /positions printed "—" in the SL column while Dhan held a live Forever
 * order on the founder's short 200 — order 23132609081456, trigger 3354.85,
 * STOP_LOSS_LEG, status PENDING, re-armed at that morning's partial.
 *
 * The column was honest about the DATABASE and silent about reality.
 * `stop_loss_price` is NULL on every direct-exit row because pine_replica
 * owns the trailing stop and re-places it straight at Dhan without telling
 * this platform. A trader reading that dash sees an unprotected live
 * position and may act on it — the most dangerous thing this screen can
 * imply.
 *
 * The third state still matters: a stop we have NOT read is a dash, never a
 * claim that there is no stop.
 */

import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

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

vi.mock("@/hooks/useSystemMode", () => ({
  useSystemMode: () => ({
    paper_mode: false,
    kill_switch_check_enabled: true,
    circuit_breaker_enabled: true,
  }),
}));

const apiData = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));
vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => {
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

import PositionsPage from "@/app/(dashboard)/positions/page";

const LIVE_STRATEGY = "89423ecc-c76e-432c-b107-0791508542f0";

const STRATEGIES = {
  strategies: [{ id: LIVE_STRATEGY, name: "BSE LTD Futures", is_paper: false }],
  count: 1,
};

/** The founder's actual live row on 2026-09-09. */
function shortPosition(over: Record<string, unknown> = {}) {
  return {
    id: "d0086394-e66b-4b49-b557-7c337df777ac",
    strategy_id: LIVE_STRATEGY,
    symbol: "BSE-SEP2026-FUT",
    side: "sell",
    total_quantity: 400,
    remaining_quantity: 200,
    avg_entry_price: "3393.1500",
    target_price: null,
    stop_loss_price: null, // our column really is NULL — pine_replica owns it
    highest_price_seen: null,
    status: "partial",
    opened_at: "2026-09-08T08:30:11Z",
    closed_at: null,
    final_pnl: null,
    ...over,
  };
}

function renderWith(position: Record<string, unknown>) {
  apiData.current = {
    "/strategies": STRATEGIES,
    "/strategies/positions": { positions: [position], count: 1 },
  };
  render(<PositionsPage />);
  return screen.getByText("BSE-SEP2026-FUT").closest("tr")!;
}

beforeEach(() => {
  apiData.current = {};
});
afterEach(() => {
  cleanup();
});

describe("the SL column tells the truth about protection", () => {
  it("🔴 shows the stop resting at the broker when our own column is NULL", () => {
    const row = renderWith(
      shortPosition({
        broker_stop_price: "3354.8500",
        broker_stop_order_id: "23132609081456",
      }),
    );

    const stop = within(row).getByTestId("broker-resting-stop");
    expect(stop.textContent ?? "").toContain("3,355");
    // Labelled as the broker's, not ours — the two are different facts.
    expect(stop.textContent ?? "").toMatch(/broker/i);
    // The order id is available for verification against Dhan.
    expect(stop.getAttribute("title") ?? "").toContain("23132609081456");
  });

  it("🔴 keeps the dash when no stop has been read — never 'no stop'", () => {
    // Empty cache means UNKNOWN. Asserting "unprotected" on the strength of
    // a cache miss would be the same class of lie in the other direction.
    const row = renderWith(shortPosition());

    expect(within(row).queryByTestId("broker-resting-stop")).toBeNull();
    expect(within(row).getAllByText("—").length).toBeGreaterThan(0);
  });

  it("prefers our OWN stop when the row actually carries one", () => {
    const row = renderWith(
      shortPosition({
        stop_loss_price: "3300.0000",
        broker_stop_price: "3354.8500",
        broker_stop_order_id: "23132609081456",
      }),
    );

    expect(within(row).queryByTestId("broker-resting-stop")).toBeNull();
    expect(within(row).getByText("₹3,300")).toBeInTheDocument();
  });

  it("🔴 treats a zero broker stop as unknown, not as a stop at ₹0", () => {
    const row = renderWith(shortPosition({ broker_stop_price: "0.0000" }));

    expect(within(row).queryByTestId("broker-resting-stop")).toBeNull();
    expect(within(row).queryByText("₹0")).toBeNull();
  });
});
