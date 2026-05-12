/**
 * Component interaction tests — R5 critical-path coverage.
 *
 * Day-5 scope: render the component, click the critical interactions
 * (typing a symbol, picking a quick-pick, switching timeframe, retry
 * on error). Snapshot-style assertions only — visual polish is Day 4.
 */

import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorState } from "@/components/chart/ErrorState";
import { LoadingState } from "@/components/chart/LoadingState";
import { SymbolSelector } from "@/components/chart/SymbolSelector";
import { TimeframeSelector } from "@/components/chart/TimeframeSelector";

describe("SymbolSelector", () => {
  it("renders the input + quick picks", () => {
    render(<SymbolSelector value="NIFTY" onChange={() => {}} />);
    expect(screen.getByTestId("symbol-input")).toBeInTheDocument();
    expect(screen.getByTestId("symbol-quick-NIFTY")).toBeInTheDocument();
    expect(screen.getByTestId("symbol-quick-BANKNIFTY")).toBeInTheDocument();
  });

  it("clicking a quick-pick calls onChange with the value", () => {
    const spy = vi.fn();
    render(<SymbolSelector value="NIFTY" onChange={spy} />);
    fireEvent.click(screen.getByTestId("symbol-quick-BANKNIFTY"));
    expect(spy).toHaveBeenCalledWith("BANKNIFTY");
  });

  it("typing uppercases the value", () => {
    const spy = vi.fn();
    render(<SymbolSelector value="" onChange={spy} />);
    fireEvent.change(screen.getByTestId("symbol-input"), {
      target: { value: "reliance" },
    });
    expect(spy).toHaveBeenCalledWith("RELIANCE");
  });

  it("blur trims + uppercases", () => {
    const spy = vi.fn();
    render(<SymbolSelector value="  nifty  " onChange={spy} />);
    fireEvent.blur(screen.getByTestId("symbol-input"), {
      target: { value: "  nifty  " },
    });
    expect(spy).toHaveBeenCalledWith("NIFTY");
  });
});

describe("TimeframeSelector", () => {
  it("renders all 5 supported timeframes", () => {
    render(<TimeframeSelector value="5m" onChange={() => {}} />);
    for (const tf of ["1m", "5m", "15m", "1h", "1d"]) {
      expect(screen.getByTestId(`timeframe-${tf}`)).toBeInTheDocument();
    }
  });

  it("marks the active timeframe with aria-checked", () => {
    render(<TimeframeSelector value="15m" onChange={() => {}} />);
    expect(screen.getByTestId("timeframe-15m")).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByTestId("timeframe-5m")).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("clicking a timeframe calls onChange", () => {
    const spy = vi.fn();
    render(<TimeframeSelector value="5m" onChange={spy} />);
    fireEvent.click(screen.getByTestId("timeframe-1h"));
    expect(spy).toHaveBeenCalledWith("1h");
  });
});

describe("LoadingState", () => {
  it("renders the loading container", () => {
    render(<LoadingState />);
    expect(screen.getByTestId("chart-loading")).toBeInTheDocument();
  });

  it("renders the 3-layer chart-shaped skeleton (B7)", () => {
    render(<LoadingState />);
    // Layer 1 — candle canvas placeholder (~90% of area).
    expect(
      screen.getByTestId("chart-loading-canvas"),
    ).toBeInTheDocument();
    // Layer 2 — price axis (thin vertical block, right edge).
    expect(
      screen.getByTestId("chart-loading-price-axis"),
    ).toBeInTheDocument();
    // Layer 3 — time axis (thin horizontal block, bottom edge).
    expect(
      screen.getByTestId("chart-loading-time-axis"),
    ).toBeInTheDocument();
  });

  it("places the 3 layers as direct children of the grid container", () => {
    // Snapshot-equivalent structural assertion: the grid container
    // is the outer element and has exactly 4 children (canvas, price
    // axis, time axis, blank corner). Children are asserted in the
    // test above; this one locks in the count + ordering so a future
    // layout regression (e.g. accidental extra wrapper) is caught.
    const { container } = render(<LoadingState />);
    const grid = container.firstElementChild;
    expect(grid).not.toBeNull();
    expect(grid).toHaveAttribute("data-testid", "chart-loading");
    expect(grid?.children).toHaveLength(4);
    expect(grid?.children[0]).toHaveAttribute(
      "data-testid",
      "chart-loading-canvas",
    );
    expect(grid?.children[1]).toHaveAttribute(
      "data-testid",
      "chart-loading-price-axis",
    );
    expect(grid?.children[2]).toHaveAttribute(
      "data-testid",
      "chart-loading-time-axis",
    );
    expect(grid?.children[3]).toHaveAttribute("aria-hidden", "true");
  });
});

describe("ErrorState", () => {
  it("renders fetch-error variant with Hinglish title + retry CTA", () => {
    const onRetry = vi.fn();
    render(
      <ErrorState
        kind="fetch"
        message="Backend offline"
        onRetry={onRetry}
      />,
    );
    expect(screen.getByTestId("chart-error-fetch")).toBeInTheDocument();
    expect(screen.getByText(/Chart data load nahi/i)).toBeInTheDocument();
    expect(screen.getByText("Backend offline")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("chart-error-retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("renders page-crash variant with Hinglish title + retry CTA (B6)", () => {
    const onRetry = vi.fn();
    render(
      <ErrorState
        kind="page-crash"
        message="Unexpected render error (ID: abc123)"
        onRetry={onRetry}
      />,
    );
    expect(
      screen.getByTestId("chart-error-page-crash"),
    ).toBeInTheDocument();
    expect(screen.getByText(/Chart crash ho gaya/i)).toBeInTheDocument();
    expect(
      screen.getByText("Unexpected render error (ID: abc123)"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("chart-error-retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
