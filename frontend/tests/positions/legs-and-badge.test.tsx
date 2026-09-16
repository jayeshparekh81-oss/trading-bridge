/**
 * R4 — the fills are ON THE SCREEN, and the badge is earned.
 *
 * THIS FILE EXISTS BECAUSE A SOURCE-TEXT TEST WAS NOT ENOUGH. The first R4
 * check asserted that `p.legs.map` appeared in the page source. Replacing the
 * surrounding condition with `false` — which removes the whole section from
 * the render — left that string in place, and the test happily passed. A test
 * that reads the source can prove code EXISTS; only a render can prove the
 * customer SEES it.
 *
 * What is pinned here, in the founder's words: every AUTOMATED order behind a
 * position — entry, partial, broker stop (auto), SL / trailing exit — with
 * qty, fill price, IST time and the Dhan order id, plus a verification badge
 * that may only claim what a stored truth-check run actually checked.
 *
 * The fixture is the real 844b8037 round trip of 03/04-Sep 2026.
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

/** 844b8037 — the real round trip, with the leg that pine_replica closed. */
const LEGS = [
  {
    leg_role: "entry", label: "entry", side: "buy", quantity: 800,
    price: "3270.0000", price_display: "3270.00",
    broker_order_id: "32226090368506", filled_at: "2026-09-03T04:15:17+00:00",
    filled_at_ist: "03/09/26, 09:45 am", broker_fill: true,
  },
  {
    leg_role: "direct_partial", label: "partial exit", side: "sell", quantity: 400,
    price: "3325.4000", price_display: "3325.40",
    broker_order_id: "34226090334306", filled_at: "2026-09-03T07:15:13+00:00",
    filled_at_ist: "03/09/26, 12:45 pm", broker_fill: true,
  },
  {
    // The one that matters: the ENGINE's own Forever order at Dhan.
    leg_role: "broker_stop", label: "broker stop (auto)", side: "sell", quantity: 400,
    price: "3415.5000", price_display: "3415.50",
    broker_order_id: "312260904412406", filled_at: "2026-09-04T07:41:13+00:00",
    filled_at_ist: "04/09/26, 01:11 pm", broker_fill: true,
  },
];

function closedPosition(over: Record<string, unknown> = {}) {
  return {
    id: "844b8037-f192-40f8-88ce-09b091030c17",
    strategy_id: LIVE_STRATEGY,
    symbol: "BSE-SEP2026-FUT",
    side: "buy",
    total_quantity: 800,
    remaining_quantity: 0,
    avg_entry_price: "3270.0000",
    target_price: null,
    stop_loss_price: null,
    highest_price_seen: null,
    status: "closed",
    opened_at: "2026-09-03T04:15:17Z",
    closed_at: "2026-09-04T07:41:13Z",
    final_pnl: "78057.7216",
    pnl_attribution: "bot_only",
    legs_balanced: true,
    legs: LEGS,
    verification: "verified",
    verified_on: "2026-09-04",
    ...over,
  };
}

function renderWith(position: Record<string, unknown>) {
  apiData.current = {
    "/strategies": STRATEGIES,
    "/strategies/positions": { positions: [position], count: 1 },
  };
  render(<PositionsPage />);
}

beforeEach(() => { apiData.current = {}; });
afterEach(() => { cleanup(); });

describe("every automated order is on the screen", () => {
  it("🔴 renders all three legs, including the engine's own broker stop", () => {
    renderWith(closedPosition());
    const legs = screen.getByTestId("position-legs");
    const text = legs.textContent ?? "";

    expect(text).toContain("entry");
    expect(text).toContain("partial exit");
    // pine_replica's Forever order CLOSED this trade. Before R4 it was invisible.
    expect(text).toContain("broker stop (auto)");
  });

  it("each leg carries qty, fill price, IST time and the Dhan order id", () => {
    renderWith(closedPosition());
    const text = screen.getByTestId("position-legs").textContent ?? "";

    expect(text).toContain("800");
    expect(text).toContain("3415.50");
    expect(text).toContain("04/09/26, 01:11 pm");
    expect(text).toContain("312260904412406");
  });

  it("the time is IST, not the raw UTC instant", () => {
    // The C5 render printed 2026-09-04T07:41:13 beside rows in local time.
    // Two clocks on one page is worse than either alone: the engine's 13:11
    // stop looked like it fired at 7am.
    renderWith(closedPosition());
    const text = screen.getByTestId("position-legs").textContent ?? "";
    expect(text).toContain("01:11 pm");
    expect(text).not.toContain("07:41");
  });

  it("the price shows two decimals", () => {
    renderWith(closedPosition());
    const text = screen.getByTestId("position-legs").textContent ?? "";
    expect(text).toContain("3270.00");
  });

  it("falsification twin: a position with no legs renders no legs section", () => {
    // A section that appeared unconditionally — with empty rows — would pass
    // every assertion above while telling the reader nothing.
    renderWith(closedPosition({ legs: [] }));
    expect(screen.queryByTestId("position-legs")).toBeNull();
  });

  it("falsification twin: a leg with no fill of its own prints a dash", () => {
    renderWith(
      closedPosition({
        legs: [
          {
            leg_role: "manual_close", label: "manual close (Dhan app)",
            side: "buy", quantity: 200, price: null, price_display: null,
            broker_order_id: "35226091145606", filled_at_ist: "11/09/26, 09:31 am",
            broker_fill: true,
          },
        ],
      }),
    );
    const text = screen.getByTestId("position-legs").textContent ?? "";
    expect(text).toContain("—");
    expect(text).not.toContain("0.00");
  });
});

describe("the verification badge claims only what was checked", () => {
  it("a verified row shows the badge WITH the run's date", () => {
    renderWith(closedPosition());
    const badge = screen.getByTestId("verify-verified");
    expect(badge.textContent ?? "").toContain("Dhan se verified");
    expect(badge.textContent ?? "").toContain("2026-09-04");
  });

  it("🔴 a hand-closed row says 'manual se band', never 'verify baaki'", () => {
    // d0086394. Promising a ✅ that can never arrive is the lie R1.3 removes:
    // by the founder's rule this trade's P&L is not counted at all.
    renderWith(closedPosition({ verification: "manual_closed", final_pnl: null }));
    expect(screen.getByTestId("verify-manual-closed").textContent).toContain(
      "manual se band",
    );
    expect(screen.queryByTestId("verify-verified")).toBeNull();
    expect(screen.queryByTestId("verify-pending")).toBeNull();
  });

  it("an unchecked row admits it has not been checked", () => {
    renderWith(closedPosition({ verification: "pending", verified_on: null }));
    expect(screen.getByTestId("verify-pending").textContent).toContain(
      "Dhan se verify baaki",
    );
    expect(screen.queryByTestId("verify-verified")).toBeNull();
  });

  it("falsification twin: the badge is NOT rendered for every row regardless", () => {
    // If the ✅ appeared unconditionally, the page would claim Dhan had
    // verified rows nobody had ever compared with the broker.
    renderWith(closedPosition({ verification: "pending" }));
    expect(screen.queryByTestId("verify-verified")).toBeNull();
  });
});

describe("an unbilled row shows gross and says the charges are coming", () => {
  it("prints gross with 'charges baaki' and no net", () => {
    renderWith(
      closedPosition({
        final_pnl: null,
        derived_gross_pnl: "80360.00",
        derived_realised_charges: null,
        verification: "pending",
      }),
    );
    const cell = screen.getByTestId("pnl-gross-only");
    expect(cell.textContent ?? "").toContain("charges baaki");
    expect(cell.textContent ?? "").toMatch(/80,360/);
  });

  it("falsification twin: once billed, it says where the charges came from", () => {
    renderWith(
      closedPosition({
        final_pnl: null,
        derived_gross_pnl: "80360.00",
        derived_realised_charges: "2302.2784",
        verification: "pending",
      }),
    );
    const cell = screen.getByTestId("pnl-gross-only");
    expect(cell.textContent ?? "").toContain("Dhan ke bill se");
    expect(cell.textContent ?? "").not.toContain("baaki");
  });
});

describe("the duplicate exit is shown, and counted", () => {
  const DUP = {
    broker_order_id: "23226090443106",
    side: "sell",
    qty: 400,
    price: "3415.80",
    gross_pnl: "-4360.00",
    // Dhan billed the accidental sell AND both closing buys. Counting only the
    // gross here put the founder's headline 133.13 too high — found by the R4
    // render, not by reading the code.
    billed_charges: "133.1296",
    net_pnl: "-4493.1296",
    label: "system galti: duplicate exit",
    reason:
      "13:11:13 engine stop child took this position to zero. 13:15:12 the platform SL fired anyway and OPENED A SHORT 400 FROM FLAT.",
  };

  it("🔴 renders it apart from the position's own legs, with its own number", () => {
    // It is NOT this position's exit — pricing the position against it would
    // use a fill that belongs to a different, accidental trade.
    renderWith(closedPosition({ duplicate_exit: DUP }));
    const dup = screen.getByTestId("duplicate-exit");
    expect(dup.textContent ?? "").toContain("system galti: duplicate exit");
    expect(dup.textContent ?? "").toContain("23226090443106");
    expect(dup.textContent ?? "").toMatch(/4,360/);
  });

  it("its loss is COUNTED in both totals", () => {
    // A bug that cost money is part of the record. Gross with gross, net with
    // net — 80,360 gross and 78,057.72 net, each less the 4,360.
    renderWith(
      closedPosition({ derived_gross_pnl: "80360.00", duplicate_exit: DUP }),
    );
    const gross = screen.getByTestId("total-gross").textContent ?? "";
    const net = screen.getByTestId("total-net").textContent ?? "";
    // Gross with gross, net with net. 80,360 - 4,360 = 76,000 gross;
    // 78,057.7216 - 4,493.1296 = 73,564.592 -> ₹73,565 net.
    expect(gross).toMatch(/76,000/);
    expect(net).toMatch(/73,565/);
  });

  it("falsification twin: a position without one renders no duplicate row", () => {
    renderWith(closedPosition());
    expect(screen.queryByTestId("duplicate-exit")).toBeNull();
  });
});

describe("A1 — the two totals are separate, and never mixed", () => {
  it("gross and net are rendered as distinct figures", () => {
    renderWith(closedPosition({ derived_gross_pnl: "80360.00" }));
    expect(screen.getByTestId("total-gross").textContent).toMatch(/TOTAL GROSS/);
    expect(screen.getByTestId("total-net").textContent).toMatch(/TOTAL NET/);
    expect(screen.getByTestId("total-gross").textContent).toMatch(/80,360/);
    expect(screen.getByTestId("total-net").textContent).toMatch(/78,058/);
  });

  it("🔴 an unbilled row makes TOTAL NET say 'baaki', never a partial sum", () => {
    // Summing the rows that happen to be billed and calling it the total
    // understates charges and overstates net — quietly, and always in the
    // flattering direction.
    renderWith(
      closedPosition({ final_pnl: null, derived_gross_pnl: "80360.00" }),
    );
    const net = screen.getByTestId("total-net").textContent ?? "";
    expect(net).toContain("baaki");
    expect(net).not.toMatch(/₹/);
    // …while gross is still perfectly knowable and still shown.
    expect(screen.getByTestId("total-gross").textContent).toMatch(/80,360/);
  });

  it("falsification twin: an empty page prints no confident zero", () => {
    apiData.current = {
      "/strategies": STRATEGIES,
      "/strategies/positions": { positions: [], count: 0 },
    };
    render(<PositionsPage />);
    expect(screen.queryByTestId("positions-totals")).toBeNull();
  });
});


describe("the duplicate exit's own charges are counted too", () => {
  it("🔴 an UNBILLED duplicate exit makes the net total say 'baaki'", () => {
    // The bug the R4 render found, pinned so it cannot come back: counting
    // this row at GROSS inside a NET total inflated the headline by 133.13.
    // If its bill is missing, the total must refuse rather than mix bases.
    renderWith(
      closedPosition({
        derived_gross_pnl: "80360.00",
        duplicate_exit: {
          broker_order_id: "23226090443106", side: "sell", qty: 400,
          price: "3415.80", gross_pnl: "-4360.00",
          billed_charges: null, net_pnl: null,
          label: "system galti: duplicate exit",
        },
      }),
    );
    expect(screen.getByTestId("total-net").textContent).toContain("baaki");
    // Gross is still knowable and still shown.
    expect(screen.getByTestId("total-gross").textContent).toMatch(/76,000/);
  });

  it("falsification twin: once billed, it is counted at NET and the total resolves", () => {
    renderWith(
      closedPosition({
        derived_gross_pnl: "80360.00",
        duplicate_exit: {
          broker_order_id: "23226090443106", side: "sell", qty: 400,
          price: "3415.80", gross_pnl: "-4360.00",
          billed_charges: "133.1296", net_pnl: "-4493.1296",
          label: "system galti: duplicate exit",
        },
      }),
    );
    const net = screen.getByTestId("total-net").textContent ?? "";
    expect(net).not.toContain("baaki");
    expect(net).toMatch(/73,565/);
  });
});
