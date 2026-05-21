/**
 * BacktestChartPanel — state-machine + render contract tests.
 *
 * Queue EE / Milestone 3.
 *
 * Lightweight Charts is bypassed via the `createChartFn` injection
 * seam (same pattern used by frontend/tests/chart/CandlestickChart.test.tsx)
 * — jsdom never sees a canvas. `@/lib/api` and `@/lib/chart/api` are
 * vi.mock'd at module level so the component's fetch calls resolve
 * against per-test fakes without network or auth.
 *
 * Coverage per Queue EE brief, §Phase 4:
 *   1. loading state visible on initial mount (fetch pending)
 *   2. loaded with markers → chart created + markers passed to setMarkers
 *   3. empty markers → "No trades" empty state
 *   4. error → error banner + retry button
 *   5. retry → second fetch invoked
 *   6. marker colour mapping — entry green / exit red preserved from backend wire shape
 */

import { act, render, screen, waitFor } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";

// ── Module-level mocks ─────────────────────────────────────────────────

vi.mock("@/lib/api", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      get: vi.fn(),
      post: vi.fn(),
      put: vi.fn(),
      delete: vi.fn(),
    },
  };
});

vi.mock("@/lib/chart/api", () => ({
  fetchChartHistory: vi.fn(),
}));

import { BacktestChartPanel } from "@/components/backtest/BacktestChartPanel";
import { api, ApiError } from "@/lib/api";
import { fetchChartHistory } from "@/lib/chart/api";

// ── Fake Lightweight Charts factory ────────────────────────────────────

interface FakeChartBundle {
  chart: {
    addCandlestickSeries: Mock;
    applyOptions: Mock;
    remove: Mock;
    timeScale: Mock;
  };
  series: {
    setData: Mock;
    setMarkers: Mock;
  };
  timeScale: { fitContent: Mock };
}

function makeFakeBundle(): FakeChartBundle {
  const series = {
    setData: vi.fn(),
    setMarkers: vi.fn(),
  };
  const timeScale = { fitContent: vi.fn() };
  const chart = {
    addCandlestickSeries: vi.fn(() => series),
    applyOptions: vi.fn(),
    remove: vi.fn(),
    timeScale: vi.fn(() => timeScale),
  };
  return { chart, series, timeScale };
}

function makeFakeCreateChart(bundle: FakeChartBundle) {
  return vi.fn(() => bundle.chart) as unknown as typeof import(
    "lightweight-charts"
  ).createChart;
}

// ── Wire-shape factories ───────────────────────────────────────────────

function makeEntryMarker(time: number) {
  return {
    time,
    position: "belowBar" as const,
    color: "#22c55e", // green-500 — backend's LONG_ENTRY colour
    shape: "arrowUp" as const,
    text: "BUY",
  };
}

function makeExitMarker(time: number) {
  return {
    time,
    position: "aboveBar" as const,
    color: "#ef4444", // red-500 — backend's LONG_EXIT colour
    shape: "arrowDown" as const,
    text: "SELL",
  };
}

function makeWireCandle(timeIso: string) {
  return {
    symbol: "NIFTY",
    timeframe: "5m" as const,
    timestamp: timeIso,
    open: "100.0",
    high: "101.0",
    low: "99.5",
    close: "100.5",
    volume: 1234,
  };
}

const baseProps = {
  runId: "550e8400-e29b-41d4-a716-446655440000",
  strategyId: "89423ecc-c76e-432c-b107-0791508542f0",
  symbol: "NIFTY",
  timeframe: "5m" as const,
};

// ── Tests ──────────────────────────────────────────────────────────────

describe("BacktestChartPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the loading skeleton while fetch is in flight", async () => {
    // Pending promise — never resolves in this assertion block.
    (api.get as Mock).mockReturnValue(new Promise(() => {}));
    const fakeCreate = makeFakeCreateChart(makeFakeBundle());

    render(<BacktestChartPanel {...baseProps} createChartFn={fakeCreate} />);

    expect(
      screen.getByTestId("backtest-chart-panel-loading"),
    ).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith(
      `/backtest/${baseProps.runId}/markers`,
    );
    // Chart should NOT have been mounted yet (still in loading state).
    expect(fakeCreate).not.toHaveBeenCalled();
  });

  it("renders the chart and passes markers to setMarkers when markers + candles arrive", async () => {
    const entry = makeEntryMarker(1716000000);
    const exit = makeExitMarker(1716003600);
    (api.get as Mock).mockResolvedValue({
      run_id: baseProps.runId,
      markers: [entry, exit],
    });
    (fetchChartHistory as Mock).mockResolvedValue({
      symbol: "NIFTY",
      timeframe: "5m",
      from_ts: "2026-05-18T00:00:00Z",
      to_ts: "2026-05-18T01:00:00Z",
      cached: false,
      candles: [
        makeWireCandle("2026-05-18T00:00:00Z"),
        makeWireCandle("2026-05-18T00:05:00Z"),
      ],
    });
    const bundle = makeFakeBundle();
    const fakeCreate = makeFakeCreateChart(bundle);

    await act(async () => {
      render(<BacktestChartPanel {...baseProps} createChartFn={fakeCreate} />);
    });

    await waitFor(() => {
      expect(bundle.series.setMarkers).toHaveBeenCalled();
    });

    expect(fakeCreate).toHaveBeenCalledTimes(1);
    expect(bundle.chart.addCandlestickSeries).toHaveBeenCalledTimes(1);
    expect(bundle.series.setData).toHaveBeenCalledTimes(1);

    const setMarkersArg = (bundle.series.setMarkers as Mock).mock.calls[0][0];
    expect(setMarkersArg).toHaveLength(2);
    // Backend's LWC shape passes through unchanged (no client adapter).
    expect(setMarkersArg[0]).toEqual({
      time: entry.time,
      position: entry.position,
      color: entry.color,
      shape: entry.shape,
      text: entry.text,
    });
    expect(setMarkersArg[1]).toEqual({
      time: exit.time,
      position: exit.position,
      color: exit.color,
      shape: exit.shape,
      text: exit.text,
    });
    expect(bundle.timeScale.fitContent).toHaveBeenCalled();
  });

  it("renders the empty state when the backtest produced no markers", async () => {
    (api.get as Mock).mockResolvedValue({
      run_id: baseProps.runId,
      markers: [],
    });
    const bundle = makeFakeBundle();
    const fakeCreate = makeFakeCreateChart(bundle);

    await act(async () => {
      render(<BacktestChartPanel {...baseProps} createChartFn={fakeCreate} />);
    });

    await waitFor(() => {
      expect(
        screen.getByTestId("backtest-chart-panel-empty"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/no trades in this backtest run/i)).toBeInTheDocument();
    // No candle fetch fired (empty markers short-circuit before window derivation).
    expect(fetchChartHistory).not.toHaveBeenCalled();
    // Chart never mounted because the empty state replaces the canvas.
    expect(fakeCreate).not.toHaveBeenCalled();
  });

  it("renders the missing state when the markers endpoint returns 404", async () => {
    (api.get as Mock).mockRejectedValue(new ApiError(404, "Run not found."));
    const bundle = makeFakeBundle();
    const fakeCreate = makeFakeCreateChart(bundle);

    await act(async () => {
      render(<BacktestChartPanel {...baseProps} createChartFn={fakeCreate} />);
    });

    await waitFor(() => {
      expect(
        screen.getByTestId("backtest-chart-panel-empty"),
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(/markers not available for this run/i),
    ).toBeInTheDocument();
  });

  it("renders the error state with a retry button on generic failure, and retry refetches", async () => {
    (api.get as Mock).mockRejectedValue(new Error("boom"));
    const bundle = makeFakeBundle();
    const fakeCreate = makeFakeCreateChart(bundle);

    await act(async () => {
      render(<BacktestChartPanel {...baseProps} createChartFn={fakeCreate} />);
    });

    await waitFor(() => {
      expect(
        screen.getByTestId("backtest-chart-panel-error"),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/chart load failed/i)).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();

    const retry = screen.getByTestId("backtest-chart-panel-retry");

    // Second attempt — wire up a success path so retry takes effect.
    (api.get as Mock).mockResolvedValue({
      run_id: baseProps.runId,
      markers: [],
    });

    await act(async () => {
      retry.click();
    });

    await waitFor(() => {
      // After successful retry we land on the empty-markers state.
      expect(
        screen.getByTestId("backtest-chart-panel-empty"),
      ).toBeInTheDocument();
    });
    expect(api.get).toHaveBeenCalledTimes(2);
  });

  it("preserves the backend's per-side marker colour mapping (entry green, exit red)", async () => {
    const entry = makeEntryMarker(1716000000);
    const exit = makeExitMarker(1716003600);
    (api.get as Mock).mockResolvedValue({
      run_id: baseProps.runId,
      markers: [entry, exit],
    });
    (fetchChartHistory as Mock).mockResolvedValue({
      symbol: "NIFTY",
      timeframe: "5m",
      from_ts: "2026-05-18T00:00:00Z",
      to_ts: "2026-05-18T01:00:00Z",
      cached: false,
      candles: [makeWireCandle("2026-05-18T00:00:00Z")],
    });
    const bundle = makeFakeBundle();
    const fakeCreate = makeFakeCreateChart(bundle);

    await act(async () => {
      render(<BacktestChartPanel {...baseProps} createChartFn={fakeCreate} />);
    });

    await waitFor(() => {
      expect(bundle.series.setMarkers).toHaveBeenCalled();
    });

    const passedMarkers = (bundle.series.setMarkers as Mock).mock.calls[0][0];
    const entryMarker = passedMarkers.find((m: { text: string }) => m.text === "BUY");
    const exitMarker = passedMarkers.find((m: { text: string }) => m.text === "SELL");

    expect(entryMarker.color).toBe("#22c55e"); // green-500
    expect(entryMarker.shape).toBe("arrowUp");
    expect(entryMarker.position).toBe("belowBar");

    expect(exitMarker.color).toBe("#ef4444"); // red-500
    expect(exitMarker.shape).toBe("arrowDown");
    expect(exitMarker.position).toBe("aboveBar");
  });

  it("falls back to markers-only when the candles endpoint fails", async () => {
    const entry = makeEntryMarker(1716000000);
    (api.get as Mock).mockResolvedValue({
      run_id: baseProps.runId,
      markers: [entry],
    });
    (fetchChartHistory as Mock).mockRejectedValue(
      new Error("history endpoint down"),
    );
    const bundle = makeFakeBundle();
    const fakeCreate = makeFakeCreateChart(bundle);

    await act(async () => {
      render(<BacktestChartPanel {...baseProps} createChartFn={fakeCreate} />);
    });

    await waitFor(() => {
      expect(
        screen.getByTestId("backtest-chart-panel-candles-fallback"),
      ).toBeInTheDocument();
    });
    expect(bundle.series.setData).toHaveBeenCalledWith([]);
    expect(bundle.series.setMarkers).toHaveBeenCalled();
  });
});
