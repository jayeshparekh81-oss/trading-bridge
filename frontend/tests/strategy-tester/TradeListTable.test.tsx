/**
 * TradeListTable component tests.
 */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TradeListTable } from "@/components/strategy-tester/TradeListTable";
import type { TradeRecord } from "@/lib/strategy-tester/types";

function mkTrade(over: Partial<TradeRecord>): TradeRecord {
  return {
    entryMarkerId: over.entryMarkerId ?? "e1",
    exitMarkerId: "x1",
    symbol: "RELIANCE",
    side: "LONG",
    entryTime: 1715670000,
    exitTime: 1715673600,
    entryPrice: 2500,
    exitPrice: 2520,
    qty: 5,
    pnl: 100,
    pnlPct: 0.8,
    durationMinutes: 30,
    exitReason: "TAKE_PROFIT",
    entryTimeIso: "2026-05-14T09:15:00+00:00",
    exitTimeIso: "2026-05-14T09:45:00+00:00",
    ...over,
  };
}

describe("TradeListTable", () => {
  it("renders empty state when trades is empty", () => {
    render(<TradeListTable trades={[]} />);
    expect(screen.getByTestId("trades-empty-state")).toBeInTheDocument();
    expect(screen.queryByTestId("trades-table")).not.toBeInTheDocument();
  });

  it("renders one row per trade with symbol + price + pnl", () => {
    const trades = [
      mkTrade({ entryMarkerId: "e1", symbol: "TCS", pnl: 200 }),
      mkTrade({ entryMarkerId: "e2", symbol: "INFY", pnl: -50 }),
    ];
    render(<TradeListTable trades={trades} />);
    const rows = screen.getAllByTestId("trade-row");
    expect(rows).toHaveLength(2);
    expect(screen.getByText("TCS")).toBeInTheDocument();
    expect(screen.getByText("INFY")).toBeInTheDocument();
  });

  it("renders open-trade exit cells as — and exitReason as OPEN", () => {
    const open = mkTrade({
      entryMarkerId: "e-open",
      exitMarkerId: null,
      exitTime: null,
      exitPrice: null,
      pnl: null,
      pnlPct: null,
      durationMinutes: null,
      exitReason: null,
      exitTimeIso: null,
    });
    render(<TradeListTable trades={[open]} />);
    const row = screen.getByTestId("trade-row");
    expect(within(row).getByText("OPEN")).toBeInTheDocument();
    // Multiple ``—`` cells (exit price, pnl, duration) — assert at
    // least two occurrences within the row.
    const dashes = within(row).getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(3);
  });

  it("color-codes LONG side as profit and SHORT side as loss", () => {
    const longTrade = mkTrade({ entryMarkerId: "e-long", side: "LONG" });
    const shortTrade = mkTrade({ entryMarkerId: "e-short", side: "SHORT" });
    const { container } = render(
      <TradeListTable trades={[longTrade, shortTrade]} />,
    );
    expect(
      container.querySelectorAll(".text-profit").length,
    ).toBeGreaterThan(0);
    expect(
      container.querySelectorAll(".text-loss").length,
    ).toBeGreaterThan(0);
  });

  it("toggles sort direction when same header is clicked twice", () => {
    const trades = [
      mkTrade({ entryMarkerId: "e1", symbol: "AAA", pnl: 100 }),
      mkTrade({ entryMarkerId: "e2", symbol: "BBB", pnl: 200 }),
      mkTrade({ entryMarkerId: "e3", symbol: "CCC", pnl: -50 }),
    ];
    render(<TradeListTable trades={trades} />);
    const symbolHeader = screen.getByRole("button", { name: /Symbol/i });

    // First click → desc by symbol → CCC, BBB, AAA
    fireEvent.click(symbolHeader);
    let rows = screen.getAllByTestId("trade-row");
    expect(within(rows[0]).getByText("CCC")).toBeInTheDocument();
    expect(within(rows[2]).getByText("AAA")).toBeInTheDocument();

    // Second click → asc by symbol → AAA, BBB, CCC
    fireEvent.click(symbolHeader);
    rows = screen.getAllByTestId("trade-row");
    expect(within(rows[0]).getByText("AAA")).toBeInTheDocument();
    expect(within(rows[2]).getByText("CCC")).toBeInTheDocument();
  });

  it("sorts open trades (null pnl) to the bottom in both directions", () => {
    const trades = [
      mkTrade({
        entryMarkerId: "e-open",
        exitMarkerId: null,
        exitTime: null,
        exitPrice: null,
        pnl: null,
        pnlPct: null,
        durationMinutes: null,
        exitReason: null,
        exitTimeIso: null,
      }),
      mkTrade({ entryMarkerId: "e1", pnl: 100 }),
      mkTrade({ entryMarkerId: "e2", pnl: 200 }),
    ];
    render(<TradeListTable trades={trades} />);
    const pnlHeader = screen.getByRole("button", { name: /P&L/i });

    // Initial default sort is by entryTime desc — click pnl twice to
    // hit both directions.
    fireEvent.click(pnlHeader); // desc
    let rows = screen.getAllByTestId("trade-row");
    expect(within(rows[rows.length - 1]).getByText("OPEN")).toBeInTheDocument();

    fireEvent.click(pnlHeader); // asc
    rows = screen.getAllByTestId("trade-row");
    expect(within(rows[rows.length - 1]).getByText("OPEN")).toBeInTheDocument();
  });

  it("displays trade count badge", () => {
    const trades = [
      mkTrade({ entryMarkerId: "e1" }),
      mkTrade({ entryMarkerId: "e2" }),
    ];
    render(<TradeListTable trades={trades} />);
    expect(screen.getByText("2 trades")).toBeInTheDocument();
  });

  it("singularises the count badge for one trade", () => {
    render(<TradeListTable trades={[mkTrade({ entryMarkerId: "e1" })]} />);
    expect(screen.getByText("1 trade")).toBeInTheDocument();
  });
});
