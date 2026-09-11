/**
 * The Overview is TODAY, and every number on it must have a source.
 *
 * Three false statements are pinned here, all met on the founder's own walk.
 *
 * 1. A BARE PRICE WHERE AN AMOUNT BELONGS. "Aakhri 3 trades" printed the leg's
 *    PRICE on the right — ₹3,470 in the slot every other row on this page uses
 *    for money. An order has no P&L (a round trip does, and that lives on
 *    /positions), so the right-hand column carries the ORDER'S STATUS, and a
 *    status nobody read is a dash — never the word "pending".
 *
 * 2. ORDERS COUNTED AS LEGS. The 07-Sep entry is four legs of 200 under one
 *    broker order. Listed leg by leg it filled the "last 3" with one order and
 *    made "trades aaj" say four.
 *
 * 3. A TILE THAT DISAGREES WITH ITS OWN LIST. The "Khuli positions" tile
 *    counts open AND partial; the list under it filtered `status === "open"`
 *    alone, so the founder's half-exited d0086394 was counted and then missing
 *    from the list directly beneath the count.
 *
 * And the P&L tile: `Number(ks?.daily_pnl ?? 0)` printed a confident ₹0.00
 * whenever the kill-switch read failed. A number with no honest source is "—".
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

vi.mock("@/hooks/useSystemMode", () => ({ useSystemMode: () => null }));
// Level 4+ = the Pro overview. (Below 4 the route renders SimpleHome.)
vi.mock("@/hooks/useLadder", () => ({
  useLadderOptional: () => ({ ready: true, level: 4 }),
}));
// The signals widget owns its own surface and is tested with its own file.
vi.mock("@/widgets/conviction-signals", () => ({ ConvictionSignals: () => null }));

const apiData = vi.hoisted(() => ({
  current: {} as Record<string, unknown>,
  errors: {} as Record<string, string>,
}));
vi.mock("@/shared/api/use-api", () => ({
  useApi: (url: string | null) => {
    const key =
      url === null
        ? "__null__"
        : Object.keys({ ...apiData.current, ...apiData.errors })
            .sort((a, b) => b.length - a.length)
            .find((k) => url === k || url.startsWith(k)) ?? "__miss__";
    return {
      data: apiData.current[key] ?? null,
      isLoading: false,
      error: apiData.errors[key] ?? null,
      paywalled: false,
      paywallUrl: null,
      refetch: vi.fn(),
    };
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/",
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "t@x.com", role: "user" } }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import DashboardPage from "@/app/(dashboard)/page";

const ORDER_ID = "322260907150406";

/** One leg of the founder's four-leg 07-Sep entry. */
function leg(n: number, over: Record<string, unknown> = {}) {
  return {
    id: `exec-${n}`,
    symbol: "BSE-SEP2026-FUT",
    side: "BUY",
    quantity: 200,
    price: "3470.15",
    leg_role: "entry",
    broker_order_id: ORDER_ID,
    broker_status: null,
    // "Aaj" is the IST trading day, so the fixture is dated NOW — a fixed
    // date would make the "orders aaj" count depend on when the suite runs.
    created_at: new Date().toISOString(),
    ...over,
  };
}

const KILL_SWITCH = {
  state: "ACTIVE",
  enabled: true,
  daily_pnl: "-1250.5",
  max_daily_loss_inr: "50000",
  trades_today: 1,
  max_daily_trades: 10,
  tripped_at: null,
  trip_reason: null,
};

function base(over: Record<string, unknown> = {}) {
  return {
    "/kill-switch/status": KILL_SWITCH,
    "/strategies/positions": { positions: [], count: 0 },
    "/strategies/signals": { signals: [], count: 0 },
    "/strategies/executions": { executions: [leg(1), leg(2), leg(3), leg(4)], count: 4 },
    "/users/me/brokers": [{ id: "b1", broker_name: "dhan", is_active: true, token_expires_at: null }],
    "/strategies?": { strategies: [{ is_active: true }] },
    ...over,
  };
}

beforeEach(() => {
  apiData.current = base();
  apiData.errors = {};
});
afterEach(cleanup);

describe("Aakhri 3 trades", () => {
  it("🔴 shows ONE order of 800, not four legs of 200", () => {
    render(<DashboardPage />);
    const rows = screen.getAllByTestId("recent-order-status");
    expect(rows).toHaveLength(1);
    expect(document.body.textContent ?? "").toMatch(/800 qty/);
    expect(document.body.textContent ?? "").not.toMatch(/200 qty/);
  });

  it("🔴 never prints a bare price where an amount belongs", () => {
    render(<DashboardPage />);
    // 3470.15 is a PRICE. It must not appear as the row's right-hand value.
    for (const cell of screen.getAllByTestId("recent-order-status")) {
      expect(cell.textContent ?? "").not.toMatch(/3470|3,470|₹/);
    }
  });

  it("🔴 shows the order's status — and a dash for one nobody read", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("recent-order-status").textContent).toBe("—");
    expect(document.body.textContent ?? "").not.toMatch(/pending/i);
  });

  it("shows the broker's own word when the server derived one", () => {
    apiData.current = base({
      "/strategies/executions": {
        executions: [leg(1, { broker_status: "TRADED" }), leg(2)],
        count: 2,
      },
    });
    render(<DashboardPage />);
    expect(screen.getByTestId("recent-order-status").textContent).toBe("TRADED");
  });
});

describe("aaj ka P&L has a source, or a dash", () => {
  it("prints the kill switch's figure when we have read it", () => {
    render(<DashboardPage />);
    expect(screen.getByTestId("today-pnl").textContent ?? "").toMatch(/1,25[01]/);
  });

  it("🔴 renders a dash — never ₹0.00 — when the read failed", () => {
    apiData.current = base({ "/kill-switch/status": null });
    apiData.errors = { "/kill-switch/status": "503 Service Unavailable" };
    render(<DashboardPage />);
    expect(screen.getByTestId("today-pnl").textContent).toBe("—");
    expect(document.body.textContent ?? "").toMatch(/yeh zero nahi hai/);
  });

  it("🔴 renders a dash when the field is absent from the response", () => {
    apiData.current = base({ "/kill-switch/status": { ...KILL_SWITCH, daily_pnl: null } });
    render(<DashboardPage />);
    expect(screen.getByTestId("today-pnl").textContent).toBe("—");
  });

  it("a real zero P&L still renders as ₹0 — breakeven is a fact", () => {
    apiData.current = base({ "/kill-switch/status": { ...KILL_SWITCH, daily_pnl: "0" } });
    render(<DashboardPage />);
    expect(screen.getByTestId("today-pnl").textContent ?? "").toMatch(/₹0/);
  });

  it("counts ORDERS aaj, not legs", () => {
    render(<DashboardPage />);
    // Four legs, one broker order.
    expect(document.body.textContent ?? "").toMatch(/1 order aaj/);
    expect(document.body.textContent ?? "").not.toMatch(/4 orders aaj/);
  });
});

describe("khuli positions: the list agrees with its own tile", () => {
  const OPEN = {
    id: "a13ddeb0", symbol: "BSE-SEP2026-FUT", side: "BUY", total_quantity: 800,
    remaining_quantity: 800, avg_entry_price: "3470.15", status: "open",
    opened_at: "2026-09-07T09:34:06Z",
  };
  const PARTIAL = {
    id: "d0086394", symbol: "BSE-SEP2026-FUT", side: "SELL", total_quantity: 400,
    remaining_quantity: 200, avg_entry_price: "3390.00", status: "partial",
    opened_at: "2026-09-08T09:20:00Z",
  };

  it("🔴 a partial position appears in the list, not only in the count", () => {
    apiData.current = base({
      "/strategies/positions": { positions: [OPEN, PARTIAL], count: 2 },
    });
    render(<DashboardPage />);
    const heading = screen.getByText("Khuli positions", { selector: "h2" });
    const section = heading.closest("section");
    expect(section).toBeTruthy();
    const body = section?.textContent ?? "";
    // Both rows, and the partial says so.
    expect(body).toMatch(/800 qty/);
    expect(body).toMatch(/200 qty/);
    expect(body).toMatch(/partial/);
  });

  it("the tile's count and the list's length are the same number", () => {
    apiData.current = base({
      "/strategies/positions": { positions: [OPEN, PARTIAL], count: 2 },
    });
    render(<DashboardPage />);
    const tile = screen.getByText("Khuli positions", { selector: "p" }).nextElementSibling;
    expect(tile?.textContent).toBe("2");
    const section = screen.getByText("Khuli positions", { selector: "h2" }).closest("section");
    expect(within(section as HTMLElement).getAllByText(/qty/)).toHaveLength(2);
  });
});
