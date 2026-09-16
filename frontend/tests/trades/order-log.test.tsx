/**
 * /trades is THE BOT ORDER LOG — one row per BROKER ORDER, and it says so.
 *
 * Two false statements lived on this page and both are pinned here.
 *
 * 1. FOUR ORDERS WHERE THE BROKER HAS ONE. `strategy_executions` stores one
 *    row per leg. The founder's 07-Sep entry is FOUR rows of 200 sharing
 *    broker_order_id 322260907150406 — one order of 800 at the broker. The
 *    page listed four rows of 200 and the tiles counted four "executions", so
 *    a customer reconciling against his Dhan order book counted four orders he
 *    never placed.
 *
 * 2. "pending" FOR A STATUS NOBODY READ. The status cell fell back to the word
 *    "pending" whenever `broker_status` was null. `broker_status` the COLUMN
 *    is NULL on every live row (it is written only on the paper path), so the
 *    page asserted "pending" about orders that had long since traded. Absence
 *    is a dash. It is never a state.
 *
 * And the header: this page is not the account trade book. Manual fills are
 * not ingested, so the page must not let a customer believe they would be.
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

// No cut-off named by the server → the epoch note renders nothing, and this
// file is about the rows.
vi.mock("@/hooks/useSystemMode", () => ({ useSystemMode: () => null }));

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
  usePathname: () => "/trades",
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { id: "u1", email: "t@x.com", role: "user" } }),
}));
vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
}));

import TradesPage from "@/app/(dashboard)/trades/page";

/** The founder's 07-Sep entry: four legs of 200 under ONE broker order. */
const ORDER_ID = "322260907150406";
function leg(n: number, over: Record<string, unknown> = {}) {
  return {
    id: `exec-${n}`,
    signal_id: "sig-1",
    leg_number: n,
    leg_role: "entry",
    symbol: "BSE-SEP2026-FUT",
    side: "BUY",
    quantity: 200,
    order_type: "MARKET",
    price: "3470.15",
    broker_order_id: ORDER_ID,
    broker_status: null,
    error_code: null,
    error_message: null,
    // Deliberately out of order and in a different offset from each other:
    // the row's time must be the ORDER's, i.e. the earliest leg.
    placed_at: ["2026-09-07T09:34:08Z", "2026-09-07T09:34:06Z", "2026-09-07T09:34:07Z", "2026-09-07T09:34:09Z"][n - 1],
    completed_at: null,
    ...over,
  };
}

const FOUR_LEGS = [leg(1), leg(2), leg(3), leg(4)];

beforeEach(() => {
  apiData.current = {
    "/strategies/executions": { executions: FOUR_LEGS, count: 4 },
  };
});
afterEach(cleanup);

describe("one row per broker order", () => {
  it("🔴 renders the 07-Sep entry as ONE order of 800, not four of 200", () => {
    render(<TradesPage />);
    const rows = screen.getAllByTestId("order-row");
    expect(rows).toHaveLength(1);
    const cells = within(rows[0]).getAllByRole("cell");
    // Qty is the SUM of the legs.
    expect(cells.map((c) => c.textContent)).toContain("800");
    expect(cells.map((c) => c.textContent)).not.toContain("200");
    // The broker's own order id, once.
    expect(within(rows[0]).getByText(ORDER_ID)).toBeTruthy();
  });

  it("the row carries the ORDER's time — the first leg's, not the last read", () => {
    render(<TradesPage />);
    const row = screen.getByTestId("order-row");
    const expected = new Date("2026-09-07T09:34:06Z").toLocaleString("en-IN", {
      dateStyle: "short",
      timeStyle: "medium",
    });
    expect(within(row).getByText(expected)).toBeTruthy();
  });

  it("legs with no broker_order_id are never merged into one another", () => {
    apiData.current = {
      "/strategies/executions": {
        executions: [
          leg(1, { id: "a", broker_order_id: null }),
          leg(2, { id: "b", broker_order_id: null }),
        ],
        count: 2,
      },
    };
    render(<TradesPage />);
    // We do not know which order either belonged to. Merging on that
    // ignorance would fuse orders that were never the same order.
    expect(screen.getAllByTestId("order-row")).toHaveLength(2);
  });

  it("two different broker orders stay two rows", () => {
    apiData.current = {
      "/strategies/executions": {
        executions: [...FOUR_LEGS, leg(1, { id: "z", broker_order_id: "999", leg_role: "direct_exit" })],
        count: 5,
      },
    };
    render(<TradesPage />);
    expect(screen.getAllByTestId("order-row")).toHaveLength(2);
  });
});

describe("the tiles count ORDERS, not legs", () => {
  it("🔴 four legs of one entry are ONE order and ONE entry", () => {
    render(<TradesPage />);
    expect(screen.getByTestId("tile-orders").textContent).toBe("1");
    expect(screen.getByTestId("tile-entries").textContent).toBe("1");
    expect(screen.getByTestId("tile-exits").textContent).toBe("0");
  });

  it("says how many legs made those orders, so the smaller number is explained", () => {
    render(<TradesPage />);
    expect(screen.getByText("4 execution legs")).toBeTruthy();
  });

  it("counts an exit order under Exits", () => {
    apiData.current = {
      "/strategies/executions": {
        executions: [...FOUR_LEGS, leg(1, { id: "z", broker_order_id: "999", leg_role: "direct_exit" })],
        count: 5,
      },
    };
    render(<TradesPage />);
    expect(screen.getByTestId("tile-orders").textContent).toBe("2");
    expect(screen.getByTestId("tile-exits").textContent).toBe("1");
  });
});

describe("a status we have not read is a dash", () => {
  it("🔴 never prints the word 'pending' for a null broker_status", () => {
    render(<TradesPage />);
    expect(screen.getByTestId("status-unknown").textContent).toBe("—");
    expect(document.body.textContent ?? "").not.toMatch(/pending/i);
  });

  it("prints the broker's own word when the server derived one", () => {
    apiData.current = {
      "/strategies/executions": {
        executions: FOUR_LEGS.map((l) => ({ ...l, broker_status: "TRADED" })),
        count: 4,
      },
    };
    render(<TradesPage />);
    expect(screen.queryByTestId("status-unknown")).toBeNull();
    expect(screen.getByText("TRADED")).toBeTruthy();
  });
});

describe("the page says what it is", () => {
  it("🔴 names itself the bot's order log — and no longer disclaims the rest", () => {
    // CHANGED 2026-09-16, deliberately. This used to assert the page said
    // "Aapke manual trades yahan nahi hain, woh aapke broker mein dekhein."
    // That sentence was true of `strategy_executions` and silent about the
    // account: the engine's own resting-stop exits and the customer's Dhan-app
    // fills are real money on real positions, and six of them were invisible
    // on one contract in a fortnight. The page now carries them in a second,
    // separately-labelled section, so the disclaimer would be false.
    render(<TradesPage />);
    const body = document.body.textContent ?? "";
    expect(body).toMatch(/TRADETRI ke orders/);
    expect(body).not.toMatch(/Aapke manual trades yahan nahi hain/);
  });

  it("🔴 says whose orders these are, and does not publish the account's manual trades", () => {
    // SUPERSEDED, by the founder and not by convenience. This test used to
    // require a "Broker par hue baaki fills" section listing the account's
    // other fills. That feature was never built on either side — the backend
    // serves no `broker_fills` field at all — and Round 3 then settled it the
    // other way: "/trades: bot fills only incl. broker stop (auto); no manual,
    // no other instruments."
    //
    // The need it was meant to serve is met better elsewhere: R3's 15:50 check
    // sends a hand-placed trade to the founder's PHONE the same day, instead of
    // publishing his personal trading on a page shown to other people.
    render(<TradesPage />);
    const body = document.body.textContent ?? "";
    expect(body).toMatch(/TRADETRI ke orders/);
    expect(body).not.toMatch(/Broker par hue baaki fills/);
    // …and still does not claim the account was otherwise quiet, which was the
    // original, false disclaimer.
    expect(body).not.toMatch(/Aapke manual trades yahan nahi hain/);
  });

  it("🔴 carries no P&L column — per-trade money lives on /positions", () => {
    render(<TradesPage />);
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");
    expect(headers.some((h) => /p\s*&(?:amp;)?\s*l|profit|realis/i.test(h))).toBe(false);
    expect(headers).toEqual([
      "Placed", "Type", "Symbol", "Side", "Qty", "Price", "Broker order", "Status",
    ]);
  });
});
