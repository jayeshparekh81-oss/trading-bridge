/**
 * PaperTradeList — Day 3 / Phase 1 tests.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  markerId,
  PaperTradeList,
} from "@/components/chart/PaperTradeList";
import type { ChartMarker } from "@/lib/chart/types";

function entry(time: number, price = 22500): ChartMarker {
  return {
    kind: "ENTRY",
    time,
    price,
    quantity: 50,
    side: "BUY",
    pnl: null,
    exit_reason: null,
  };
}

function tp(time: number, price = 22580, pnl = 4000): ChartMarker {
  return {
    kind: "TP_HIT",
    time,
    price,
    quantity: 50,
    side: "BUY",
    pnl,
    exit_reason: "target",
  };
}

const baseProps = {
  isLoading: false,
  hasLoaded: true,
  error: null,
  strategySelected: true,
  highlightedMarkerId: null as string | null,
  onRowClick: vi.fn(),
  isOpen: true,
  onClose: vi.fn(),
};

describe("PaperTradeList — empty states", () => {
  it("renders the 'select a strategy' empty state when no strategy selected", () => {
    render(
      <PaperTradeList
        {...baseProps}
        markers={[]}
        strategySelected={false}
      />,
    );
    expect(screen.getByTestId("paper-trade-list-empty")).toHaveTextContent(
      /strategy select karo/i,
    );
  });

  it("renders the 'no trades' empty state when strategy selected but markers empty", () => {
    render(<PaperTradeList {...baseProps} markers={[]} />);
    expect(screen.getByTestId("paper-trade-list-empty")).toHaveTextContent(
      /koi paper trade nahi/i,
    );
  });

  it("renders the loading state while initial fetch in flight", () => {
    render(
      <PaperTradeList
        {...baseProps}
        markers={[]}
        isLoading
        hasLoaded={false}
      />,
    );
    expect(screen.getByTestId("paper-trade-list-empty")).toHaveTextContent(
      /loading/i,
    );
  });

  it("renders the error message when error is set", () => {
    render(
      <PaperTradeList
        {...baseProps}
        markers={[]}
        error={new Error("server down")}
      />,
    );
    expect(screen.getByTestId("paper-trade-list-empty")).toHaveTextContent(
      /server down/i,
    );
  });
});

describe("PaperTradeList — populated", () => {
  const markers = [entry(1_000), tp(2_000), entry(3_000)];

  it("renders one row per marker with the count in the header", () => {
    render(<PaperTradeList {...baseProps} markers={markers} />);
    expect(screen.getByTestId("paper-trade-list-rows")).toBeInTheDocument();
    expect(screen.getByText(/Paper Trades/)).toBeInTheDocument();
    expect(screen.getByText(/\(3\)/)).toBeInTheDocument();
    expect(screen.getAllByRole("row")).toHaveLength(4); // header + 3 body
  });

  it("highlighted marker row carries data-highlighted='true'", () => {
    const id = markerId(markers[1]);
    render(
      <PaperTradeList
        {...baseProps}
        markers={markers}
        highlightedMarkerId={id}
      />,
    );
    const row = screen.getByTestId(`trade-row-${id}`);
    expect(row).toHaveAttribute("data-highlighted", "true");
  });

  it("clicking a row's badge fires onRowClick with the marker", () => {
    const onRowClick = vi.fn();
    render(
      <PaperTradeList
        {...baseProps}
        markers={markers}
        onRowClick={onRowClick}
      />,
    );
    const row = screen.getByTestId(`trade-row-${markerId(markers[1])}`);
    fireEvent.click(row.querySelector("button")!);
    expect(onRowClick).toHaveBeenCalledWith(markers[1]);
  });

  it("renders ENTRY/TP_HIT/SL_HIT/EXIT badge labels distinctly", () => {
    const sl: ChartMarker = {
      kind: "SL_HIT",
      time: 4000,
      price: 22400,
      quantity: 50,
      side: "BUY",
      pnl: -3500,
      exit_reason: "stop_loss",
    };
    const ex: ChartMarker = {
      kind: "EXIT",
      time: 5000,
      price: 22500,
      quantity: 50,
      side: "BUY",
      pnl: 0,
      exit_reason: "square_off",
    };
    render(
      <PaperTradeList
        {...baseProps}
        markers={[entry(1000), tp(2000), sl, ex]}
      />,
    );
    expect(screen.getByText("ENTRY")).toBeInTheDocument();
    expect(screen.getByText("TP HIT")).toBeInTheDocument();
    expect(screen.getByText("SL HIT")).toBeInTheDocument();
    expect(screen.getByText("EXIT")).toBeInTheDocument();
  });

  it("ENTRY row renders P&L as em-dash; exit rows render coloured ₹ amount", () => {
    render(<PaperTradeList {...baseProps} markers={[entry(1000), tp(2000)]} />);
    const entryRow = screen.getByTestId(`trade-row-${markerId(entry(1000))}`);
    expect(entryRow).toHaveTextContent("—");
    const tpRow = screen.getByTestId(`trade-row-${markerId(tp(2000))}`);
    expect(tpRow).toHaveTextContent("₹4,000");
  });
});

describe("PaperTradeList — drawer", () => {
  it("close button on mobile fires onClose", () => {
    const onClose = vi.fn();
    render(
      <PaperTradeList
        {...baseProps}
        markers={[entry(1)]}
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByTestId("paper-trade-list-close"));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("data-open reflects isOpen prop", () => {
    const { rerender } = render(
      <PaperTradeList {...baseProps} markers={[entry(1)]} isOpen={false} />,
    );
    expect(screen.getByTestId("paper-trade-list")).toHaveAttribute(
      "data-open",
      "false",
    );
    rerender(
      <PaperTradeList {...baseProps} markers={[entry(1)]} isOpen={true} />,
    );
    expect(screen.getByTestId("paper-trade-list")).toHaveAttribute(
      "data-open",
      "true",
    );
  });
});

describe("markerId", () => {
  it("is stable for (kind, time) — same kind+time → same id", () => {
    expect(markerId(entry(1000))).toBe(markerId(entry(1000)));
  });

  it("differs across kind", () => {
    expect(markerId(entry(1000))).not.toBe(markerId(tp(1000)));
  });

  it("differs across time", () => {
    expect(markerId(entry(1000))).not.toBe(markerId(entry(2000)));
  });
});
