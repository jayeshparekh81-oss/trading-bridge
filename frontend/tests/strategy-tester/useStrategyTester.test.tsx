/**
 * useStrategyTester hook tests.
 *
 * Pattern mirrors :mod:`tests/chart/useChartMarkers.test.tsx` — mock
 * the api module at file level, drive the mocked fn per test. We
 * exercise the parallel-fetch shape, parse-on-success behaviour,
 * stale-response drop, and the partial-success path via
 * Promise.allSettled.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockFetchMetrics = vi.fn();
const mockFetchEquity = vi.fn();
const mockFetchTrades = vi.fn();

vi.mock("@/lib/strategy-tester/api", () => ({
  fetchStrategyTesterMetrics: (...args: unknown[]) =>
    mockFetchMetrics(...args),
  fetchStrategyTesterEquity: (...args: unknown[]) => mockFetchEquity(...args),
  fetchStrategyTesterTrades: (...args: unknown[]) => mockFetchTrades(...args),
}));

// eslint-disable-next-line import/first
import { useStrategyTester } from "@/hooks/useStrategyTester";

const happyMetrics = {
  total_pnl: "1250.00",
  win_rate_pct: 60.0,
  profit_factor: 2.1,
  total_trades: 10,
  profitable_trades: 6,
  max_drawdown_pct: 5.0,
  sharpe_ratio_proxy: 0.5,
  avg_win: "300.00",
  avg_loss: "-200.00",
  largest_win: "500.00",
  largest_loss: "-400.00",
  expectancy: "125.00",
};

const happyEquity = {
  points: [
    {
      timestamp: "2026-05-14T09:00:00+00:00",
      equity: "100000.00",
      drawdown_pct: 0,
      trade_id_or_none: null,
    },
    {
      timestamp: "2026-05-14T10:00:00+00:00",
      equity: "101250.00",
      drawdown_pct: 0,
      trade_id_or_none: "t1",
    },
  ],
  starting_equity: "100000.00",
  ending_equity: "101250.00",
  max_equity: "101250.00",
  min_equity: "100000.00",
};

const happyTrades = {
  trades: [
    {
      entry_marker_id: "e1",
      exit_marker_id: "x1",
      symbol: "RELIANCE",
      side: "LONG",
      entry_time: "2026-05-14T09:15:00+00:00",
      exit_time: "2026-05-14T09:30:00+00:00",
      entry_price: "2500.00",
      exit_price: "2520.00",
      qty: 5,
      pnl: "100.00",
      pnl_pct: 0.8,
      duration_minutes: 15,
      exit_reason: "TAKE_PROFIT",
    },
  ],
  pagination: { limit: 100, offset: 0, total: 1 },
  mode: "PAPER",
};

const baseOpts = {
  strategyId: "11111111-1111-1111-1111-111111111111",
  mode: "PAPER" as const,
};

beforeEach(() => {
  vi.useRealTimers();
  mockFetchMetrics.mockReset().mockResolvedValue(happyMetrics);
  mockFetchEquity.mockReset().mockResolvedValue(happyEquity);
  mockFetchTrades.mockReset().mockResolvedValue(happyTrades);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useStrategyTester — disabled state", () => {
  it("does not fetch when strategyId is null", () => {
    const { result } = renderHook(() =>
      useStrategyTester({ ...baseOpts, strategyId: null }),
    );
    expect(result.current.metrics).toBeNull();
    expect(result.current.equity).toBeNull();
    expect(result.current.trades).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.hasLoaded).toBe(false);
    expect(mockFetchMetrics).not.toHaveBeenCalled();
    expect(mockFetchEquity).not.toHaveBeenCalled();
    expect(mockFetchTrades).not.toHaveBeenCalled();
  });

  it("does not fetch when enabled=false", () => {
    renderHook(() => useStrategyTester({ ...baseOpts, enabled: false }));
    expect(mockFetchMetrics).not.toHaveBeenCalled();
  });
});

describe("useStrategyTester — happy path", () => {
  it("fetches all three endpoints in parallel + parses each response", async () => {
    const { result } = renderHook(() => useStrategyTester(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(mockFetchMetrics).toHaveBeenCalledTimes(1);
    expect(mockFetchEquity).toHaveBeenCalledTimes(1);
    expect(mockFetchTrades).toHaveBeenCalledTimes(1);
    expect(result.current.error).toBeNull();
    expect(result.current.metrics?.totalPnl).toBe(1250);
    expect(result.current.equity?.points).toHaveLength(2);
    expect(result.current.equity?.endingEquity).toBe(101250);
    expect(result.current.trades?.trades).toHaveLength(1);
    expect(result.current.trades?.trades[0].symbol).toBe("RELIANCE");
  });

  it("forwards mode + window + startingEquity to the fetchers", async () => {
    const { result } = renderHook(() =>
      useStrategyTester({
        ...baseOpts,
        mode: "BACKTEST",
        fromIso: "2026-05-01T00:00:00+00:00",
        toIso: "2026-05-14T00:00:00+00:00",
        startingEquity: 50000,
      }),
    );
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    const [metricsArg] = mockFetchMetrics.mock.calls[0];
    expect(metricsArg).toMatchObject({
      strategyId: baseOpts.strategyId,
      mode: "BACKTEST",
      fromIso: "2026-05-01T00:00:00+00:00",
      toIso: "2026-05-14T00:00:00+00:00",
      startingEquity: 50000,
    });
  });

  it("re-fetches on strategyId or mode change", async () => {
    const { result, rerender } = renderHook(
      (p: typeof baseOpts) => useStrategyTester(p),
      { initialProps: baseOpts },
    );
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(mockFetchMetrics).toHaveBeenCalledTimes(1);

    rerender({ ...baseOpts, mode: "BACKTEST" });
    await waitFor(() => expect(mockFetchMetrics).toHaveBeenCalledTimes(2));

    rerender({
      strategyId: "22222222-2222-2222-2222-222222222222",
      mode: "BACKTEST",
    });
    await waitFor(() => expect(mockFetchMetrics).toHaveBeenCalledTimes(3));
  });

  it("refetch() re-runs all three endpoints on demand", async () => {
    const { result } = renderHook(() => useStrategyTester(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    await act(async () => {
      await result.current.refetch();
    });
    expect(mockFetchMetrics).toHaveBeenCalledTimes(2);
    expect(mockFetchEquity).toHaveBeenCalledTimes(2);
    expect(mockFetchTrades).toHaveBeenCalledTimes(2);
  });
});

describe("useStrategyTester — partial failure", () => {
  it("metrics-only failure: equity + trades still populate, error surfaces", async () => {
    mockFetchMetrics.mockImplementation(async () => {
      throw new Error("metrics 500");
    });
    const { result } = renderHook(() => useStrategyTester(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.metrics).toBeNull();
    expect(result.current.equity).not.toBeNull();
    expect(result.current.trades).not.toBeNull();
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toMatch(/metrics 500/);
  });

  it("all three fail: every result is null, error reflects the first failure", async () => {
    mockFetchMetrics.mockImplementation(async () => {
      throw new Error("metrics 500");
    });
    mockFetchEquity.mockImplementation(async () => {
      throw new Error("equity 500");
    });
    mockFetchTrades.mockImplementation(async () => {
      throw new Error("trades 500");
    });
    const { result } = renderHook(() => useStrategyTester(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.metrics).toBeNull();
    expect(result.current.equity).toBeNull();
    expect(result.current.trades).toBeNull();
    expect(result.current.error?.message).toMatch(/metrics 500/);
  });

  it("non-Error rejection is wrapped in a generic Error", async () => {
    mockFetchMetrics.mockImplementation(async () => {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw "plain string";
    });
    const { result } = renderHook(() => useStrategyTester(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toMatch(/metrics fetch failed/i);
  });

  it("a successful refetch clears a prior error", async () => {
    let callCount = 0;
    mockFetchMetrics.mockImplementation(async () => {
      callCount += 1;
      if (callCount === 1) throw new Error("transient");
      return happyMetrics;
    });
    const { result } = renderHook(() => useStrategyTester(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.error?.message).toBe("transient");
    await act(async () => {
      await result.current.refetch();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.metrics?.totalPnl).toBe(1250);
  });
});
