/**
 * StrategyTesterPanel composition tests — exercises the
 * loading / loaded / error states by mocking the hook directly so
 * the panel logic is isolated from network + parsing concerns.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  EquityCurveResponse,
  StrategyTesterMetrics,
  TradeListResponse,
} from "@/lib/strategy-tester/types";

const mockUseStrategyTester = vi.fn();

vi.mock("@/hooks/useStrategyTester", () => ({
  useStrategyTester: (...args: unknown[]) => mockUseStrategyTester(...args),
}));

// eslint-disable-next-line import/first
import { StrategyTesterPanel } from "@/components/strategy-tester/StrategyTesterPanel";

const happyMetrics: StrategyTesterMetrics = {
  totalPnl: 1250,
  winRatePct: 60,
  profitFactor: 2.1,
  totalTrades: 10,
  profitableTrades: 6,
  maxDrawdownPct: 5,
  sharpeRatioProxy: 0.5,
  avgWin: 300,
  avgLoss: -200,
  largestWin: 500,
  largestLoss: -400,
  expectancy: 125,
};

const happyEquity: EquityCurveResponse = {
  points: [
    {
      time: 1715670000,
      timestamp: "2026-05-14T09:00:00+00:00",
      equity: 100000,
      drawdownPct: 0,
      tradeId: null,
    },
  ],
  startingEquity: 100000,
  endingEquity: 101250,
  maxEquity: 101250,
  minEquity: 100000,
};

const happyTrades: TradeListResponse = {
  trades: [
    {
      entryMarkerId: "e1",
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
    },
  ],
  pagination: { limit: 100, offset: 0, total: 1 },
  mode: "PAPER",
};

function setHookState(
  over: Partial<{
    metrics: StrategyTesterMetrics | null;
    equity: EquityCurveResponse | null;
    trades: TradeListResponse | null;
    isLoading: boolean;
    hasLoaded: boolean;
    error: Error | null;
    refetch: () => Promise<void>;
  }>,
) {
  mockUseStrategyTester.mockReturnValue({
    metrics: null,
    equity: null,
    trades: null,
    isLoading: false,
    hasLoaded: false,
    error: null,
    refetch: vi.fn(async () => {}),
    ...over,
  });
}

beforeEach(() => {
  mockUseStrategyTester.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("StrategyTesterPanel", () => {
  it("shows the loading skeleton on initial fetch (isLoading + !hasLoaded)", () => {
    setHookState({ isLoading: true, hasLoaded: false });
    render(<StrategyTesterPanel strategyId="abc" mode="PAPER" />);
    expect(
      screen.getByTestId("strategy-tester-skeleton"),
    ).toBeInTheDocument();
  });

  it("renders metrics + equity + trades when all data resolves", () => {
    setHookState({
      metrics: happyMetrics,
      equity: happyEquity,
      trades: happyTrades,
      hasLoaded: true,
    });
    render(<StrategyTesterPanel strategyId="abc" mode="PAPER" />);
    expect(screen.getByTestId("metrics-header")).toBeInTheDocument();
    expect(screen.getByTestId("equity-chart-canvas")).toBeInTheDocument();
    expect(screen.getByTestId("trades-table")).toBeInTheDocument();
    expect(screen.queryByTestId("strategy-tester-skeleton")).toBeNull();
  });

  it("renders the empty trades state when trades is null", () => {
    setHookState({
      metrics: happyMetrics,
      equity: happyEquity,
      trades: null,
      hasLoaded: true,
    });
    render(<StrategyTesterPanel strategyId="abc" mode="PAPER" />);
    expect(screen.getByTestId("trades-empty-state")).toBeInTheDocument();
  });

  it("renders the metrics empty state when metrics is null", () => {
    setHookState({
      metrics: null,
      equity: null,
      trades: null,
      hasLoaded: true,
    });
    render(<StrategyTesterPanel strategyId="abc" mode="PAPER" />);
    expect(screen.getByTestId("metrics-empty-state")).toBeInTheDocument();
  });

  it("surfaces an error banner with retry button when error is set", () => {
    const refetch = vi.fn(async () => {});
    setHookState({
      error: new Error("backend down"),
      hasLoaded: true,
      refetch,
    });
    render(<StrategyTesterPanel strategyId="abc" mode="PAPER" />);
    expect(screen.getByText("Failed to load data")).toBeInTheDocument();
    expect(screen.getByText("backend down")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Retry"));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the mode badge with the correct label", () => {
    setHookState({
      metrics: happyMetrics,
      equity: happyEquity,
      trades: happyTrades,
      hasLoaded: true,
    });
    render(<StrategyTesterPanel strategyId="abc" mode="LIVE" />);
    expect(screen.getByText("LIVE")).toBeInTheDocument();
  });

  it("refresh button invokes refetch", () => {
    const refetch = vi.fn(async () => {});
    setHookState({
      metrics: happyMetrics,
      equity: happyEquity,
      trades: happyTrades,
      hasLoaded: true,
      refetch,
    });
    render(<StrategyTesterPanel strategyId="abc" mode="PAPER" />);
    fireEvent.click(screen.getByLabelText("Refresh"));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("forwards strategyId + mode + window + startingEquity to the hook", () => {
    setHookState({ hasLoaded: true });
    render(
      <StrategyTesterPanel
        strategyId="abc"
        mode="BACKTEST"
        fromIso="2026-05-01T00:00:00+00:00"
        toIso="2026-05-14T00:00:00+00:00"
        startingEquity={50000}
        tradeLimit={50}
      />,
    );
    expect(mockUseStrategyTester).toHaveBeenCalledWith(
      expect.objectContaining({
        strategyId: "abc",
        mode: "BACKTEST",
        fromIso: "2026-05-01T00:00:00+00:00",
        toIso: "2026-05-14T00:00:00+00:00",
        startingEquity: 50000,
        limit: 50,
      }),
    );
  });
});
