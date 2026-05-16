/**
 * MetricsHeader component tests.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricsHeader } from "@/components/strategy-tester/MetricsHeader";
import type { StrategyTesterMetrics } from "@/lib/strategy-tester/types";

const baseMetrics: StrategyTesterMetrics = {
  totalPnl: 1250,
  winRatePct: 60.0,
  profitFactor: 2.1,
  totalTrades: 10,
  profitableTrades: 6,
  maxDrawdownPct: 5.0,
  sharpeRatioProxy: 0.5,
  avgWin: 300,
  avgLoss: -200,
  largestWin: 500,
  largestLoss: -400,
  expectancy: 125,
};

describe("MetricsHeader", () => {
  it("renders all metric labels", () => {
    render(<MetricsHeader metrics={baseMetrics} />);
    expect(screen.getByText("Total P&L")).toBeInTheDocument();
    expect(screen.getByText("Win Rate")).toBeInTheDocument();
    expect(screen.getByText("Profit Factor")).toBeInTheDocument();
    expect(screen.getByText("Trades")).toBeInTheDocument();
    expect(screen.getByText("Max Drawdown")).toBeInTheDocument();
    expect(screen.getByText("Sharpe (per-trade)")).toBeInTheDocument();
    expect(screen.getByText("Expectancy")).toBeInTheDocument();
    expect(screen.getByText("Avg Win")).toBeInTheDocument();
    expect(screen.getByText("Avg Loss")).toBeInTheDocument();
    expect(screen.getByText("Largest Win")).toBeInTheDocument();
    expect(screen.getByText("Largest Loss")).toBeInTheDocument();
    expect(screen.getByText("Profitable")).toBeInTheDocument();
  });

  it("formats Total P&L with rupee sign and 2 decimals", () => {
    render(<MetricsHeader metrics={baseMetrics} />);
    expect(screen.getByText("+₹1,250.00")).toBeInTheDocument();
  });

  it("renders ∞ for profit_factor=null (no losers)", () => {
    render(
      <MetricsHeader metrics={{ ...baseMetrics, profitFactor: null }} />,
    );
    expect(screen.getByText("∞")).toBeInTheDocument();
  });

  it("renders — for sharpe=null (insufficient sample)", () => {
    render(
      <MetricsHeader
        metrics={{ ...baseMetrics, sharpeRatioProxy: null }}
      />,
    );
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders profit-coloured Total P&L when positive", () => {
    const { container } = render(<MetricsHeader metrics={baseMetrics} />);
    const profitTile = container.querySelector(".text-profit");
    expect(profitTile).not.toBeNull();
  });

  it("renders loss-coloured Total P&L when negative", () => {
    const { container } = render(
      <MetricsHeader metrics={{ ...baseMetrics, totalPnl: -500 }} />,
    );
    const lossTile = container.querySelector(".text-loss");
    expect(lossTile).not.toBeNull();
  });

  it("renders profitable/total ratio cell", () => {
    render(<MetricsHeader metrics={baseMetrics} />);
    expect(screen.getByText("6/10")).toBeInTheDocument();
  });

  it("accent escalates Max Drawdown to loss color above 20%", () => {
    const { container } = render(
      <MetricsHeader
        metrics={{ ...baseMetrics, maxDrawdownPct: 25, totalPnl: 0 }}
      />,
    );
    // At least the max-drawdown tile should now carry the loss class.
    expect(container.querySelectorAll(".text-loss").length).toBeGreaterThan(0);
  });

  it("supports a custom className passthrough", () => {
    render(
      <MetricsHeader metrics={baseMetrics} className="custom-grid-cls" />,
    );
    const root = screen.getByTestId("metrics-header");
    expect(root.className).toContain("custom-grid-cls");
  });
});
