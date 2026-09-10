/**
 * A closed position that never says WHEN it closed.
 *
 * `/api/strategies/positions` has always returned `closed_at`; nothing on the
 * page rendered it, so the only time a customer could see was the entry's.
 * A row reading "closed" with a September opening date and no closing one is
 * unreconcilable against a broker statement — and on the founder's own three
 * post-cut positions (844b8037, a13ddeb0 closed; d0086394 partial) that is
 * exactly the column he went looking for.
 *
 * The third state still holds: an OPEN row has no closing time, and that is a
 * dash, never a fabricated one. The exit price and the close reason are NOT
 * invented here — they arrive from the backend or they do not appear.
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

/** The founder's two closed post-cut positions, and the open half of a third. */
const CLOSED_AT = "2026-09-08T09:59:07Z";
function position(over: Record<string, unknown> = {}) {
  return {
    id: "844b8037-0000-0000-0000-000000000001",
    strategy_id: LIVE_STRATEGY,
    symbol: "BSE-SEP2026-FUT",
    side: "buy",
    total_quantity: 800,
    remaining_quantity: 0,
    avg_entry_price: "3470.15",
    target_price: null,
    stop_loss_price: null,
    highest_price_seen: null,
    status: "closed",
    opened_at: "2026-09-07T09:34:06Z",
    closed_at: CLOSED_AT,
    final_pnl: "-12500.25",
    ...over,
  };
}

beforeEach(() => {
  apiData.current = {
    "/strategies/positions": { positions: [position()], count: 1 },
    "/strategies": STRATEGIES,
  };
});
afterEach(cleanup);

describe("the Closed column", () => {
  it("🔴 renders the closed_at the API already returns", () => {
    render(<PositionsPage />);
    const cell = screen.getByTestId("position-closed-at");
    expect(cell.textContent).toBe(
      new Date(CLOSED_AT).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "short" }),
    );
  });

  it("the table has a Closed header, next to Opened", () => {
    render(<PositionsPage />);
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");
    expect(headers).toContain("Closed");
    expect(headers.indexOf("Closed")).toBe(headers.indexOf("Opened") + 1);
  });

  it("🔴 an open row shows a dash — never a closing time it does not have", () => {
    apiData.current = {
      "/strategies/positions": {
        positions: [position({ status: "open", remaining_quantity: 800, closed_at: null, final_pnl: null })],
        count: 1,
      },
      "/strategies": STRATEGIES,
    };
    render(<PositionsPage />);
    expect(screen.getByTestId("position-closed-at").textContent).toBe("—");
  });

  it("does not fabricate an exit price or a close reason client-side", () => {
    render(<PositionsPage />);
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");
    // Those columns arrive from the backend when they arrive. Nothing here
    // may derive them from the entry price and a guess.
    expect(headers.some((h) => /exit price/i.test(h))).toBe(false);
    expect(headers.some((h) => /close reason|reason/i.test(h))).toBe(false);
  });

  it("the closing time sits on the same row as its own position", () => {
    apiData.current = {
      "/strategies/positions": {
        positions: [
          position(),
          position({ id: "d0086394", status: "partial", remaining_quantity: 200, closed_at: null }),
        ],
        count: 2,
      },
      "/strategies": STRATEGIES,
    };
    render(<PositionsPage />);
    const cells = screen.getAllByTestId("position-closed-at");
    expect(cells).toHaveLength(2);
    expect(cells[1].textContent).toBe("—");
    const partialRow = cells[1].closest("tr") as HTMLElement;
    expect(within(partialRow).getByText("partial")).toBeTruthy();
  });
});
