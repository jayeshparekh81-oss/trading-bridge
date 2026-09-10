/**
 * "Nothing has been priced yet" is not "the bot made ₹0".
 *
 * `GET /api/users/me/trades/stats` answers honestly when no round trip has a
 * price: `priced_trades: 0`, and then `total_pnl` is the sum of an empty set
 * ("0") and `win_rate` the rate over an empty set (0). The page printed those
 * straight — "+₹0" under "Total P&L (priced)" and "0%" under "Win rate" — and
 * a customer reads that as a bot that traded and made exactly nothing.
 *
 * It is the same class of statement the rest of this codebase already refuses
 * to make: a zero that means "we could not read it" (price sentinels,
 * `rupees(null)`, the outage dashes). Absence renders as "—", and the page
 * says WHY, so the dash cannot itself be misread as breakage.
 *
 * The round-trip COUNT is deliberately excluded: that number we do have, and
 * it is what explains the dashes.
 */

import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

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

const apiData = vi.hoisted(() => ({
  current: {} as Record<string, unknown>,
  loading: { current: false } as { current: boolean },
}));
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
  usePathname: () => "/analytics",
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "t@x.com", role: "user" } }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import AnalyticsPage from "@/app/(dashboard)/analytics/page";

/** The shape the endpoint really sends when nothing is priced. */
function stats(over: Record<string, unknown> = {}) {
  return {
    total_trades: 3,
    priced_trades: 0,
    unpriced_trades: 3,
    executions_total: 9,
    total_pnl: "0",
    win_rate: 0,
    avg_pnl_per_trade: "0",
    best_trade_pnl: "0",
    worst_trade_pnl: "0",
    pnl_basis: "closed_round_trips",
    curve: [],
    ...over,
  };
}

/** The money cards, by their labels. */
const MONEY_CARDS = [
  "Total P&L (priced)",
  "Win rate (priced)",
  "Avg P&L / round trip",
  "Best round trip",
  "Worst round trip",
];

function cardValue(label: string): string {
  // The label and the value are siblings inside the card.
  const el = screen.getByText(label);
  return el.nextElementSibling?.textContent ?? "";
}

beforeEach(() => {
  apiData.current = {
    "/users/me/trades/stats": stats(),
    "/users/me/trades": { trades: [], total: 0 },
  };
});
afterEach(cleanup);

describe("priced_trades === 0", () => {
  it("🔴 every money card renders a dash, never ₹0 or 0%", () => {
    render(<AnalyticsPage />);
    for (const label of MONEY_CARDS) {
      expect(cardValue(label), `${label} must not fabricate a result`).toBe("—");
    }
  });

  it("🔴 says WHY the dashes are there, and that a dash is not zero", () => {
    render(<AnalyticsPage />);
    const note = screen.getByTestId("nothing-priced-note").textContent ?? "";
    expect(note).toMatch(/priced nahi hua/);
    expect(note).toMatch(/zero nahi hai/);
    // It names the round trips we DO know about.
    expect(note).toMatch(/3 round trip/);
  });

  it("still shows the round-trip COUNT — that number we have", () => {
    render(<AnalyticsPage />);
    expect(cardValue("Round trips")).toBe("3");
  });

  it("does not colour a dash as a profit or a loss", () => {
    render(<AnalyticsPage />);
    for (const label of MONEY_CARDS) {
      const cls = screen.getByText(label).nextElementSibling?.className ?? "";
      expect(cls).not.toMatch(/text-profit|text-loss/);
    }
  });
});

describe("priced_trades > 0", () => {
  beforeEach(() => {
    apiData.current = {
      "/users/me/trades/stats": stats({
        priced_trades: 2,
        unpriced_trades: 1,
        total_pnl: "-175887.89",
        win_rate: 50,
        avg_pnl_per_trade: "-87943.945",
        best_trade_pnl: "12000",
        worst_trade_pnl: "-187887.89",
      }),
      "/users/me/trades": { trades: [], total: 0 },
    };
  });

  it("prints the real numbers — the dash rule is about absence, not about loss", () => {
    render(<AnalyticsPage />);
    expect(cardValue("Total P&L (priced)")).toMatch(/1,75,887|175,887/);
    expect(cardValue("Win rate (priced)")).toBe("50%");
    expect(screen.queryByTestId("nothing-priced-note")).toBeNull();
  });

  it("a genuine breakeven still renders ₹0 — a real zero is a real fact", () => {
    apiData.current = {
      "/users/me/trades/stats": stats({ priced_trades: 1, unpriced_trades: 0, total_pnl: "0", win_rate: 0 }),
      "/users/me/trades": { trades: [], total: 0 },
    };
    render(<AnalyticsPage />);
    expect(cardValue("Total P&L (priced)")).toBe("₹0");
    expect(cardValue("Win rate (priced)")).toBe("0%");
  });
});
