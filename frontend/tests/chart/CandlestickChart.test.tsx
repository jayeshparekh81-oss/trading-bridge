/**
 * CandlestickChart — tests via the ``createChartFn`` injection seam
 * + a capturing ResizeObserver replacement.
 *
 * The component is a thin Lightweight Charts wrapper, so the tests
 * focus on the seams the component owns:
 *
 *   - mount: createChartFn called with container + width/height +
 *     theme; addCandlestickSeries called with the candle colour
 *     config; ResizeObserver constructed and observing the container.
 *   - resize (R1): firing the captured ResizeObserver callback
 *     synchronously triggers chart.applyOptions with the new
 *     contentRect width/height.
 *   - data sync: first paint → setData (full); same-or-later tail →
 *     update (O(1)); earlier tail (symbol/timeframe switch) →
 *     setData fallback; empty candles → setData([]).
 *   - unmount: observer.disconnect + chart.remove, both safe even
 *     when remove throws.
 *
 * Lightweight Charts itself is never imported by the test — the
 * createChartFn seam means jsdom never sees a canvas.
 */

import { act, render, screen } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";

import {
  CandlestickChart,
  ChartTooltip,
} from "@/components/chart/CandlestickChart";
import type { Candle } from "@/lib/chart/types";

// ─── Fake Lightweight Charts factory ──────────────────────────────────

// Capture the crosshair handler the component subscribes — tests
// fire it manually to simulate hover/leave because Lightweight Charts
// is not actually rendered in jsdom.
type CrosshairHandler = (param: {
  point?: { x: number; y: number };
  time?: number;
}) => void;

interface FakeChartBundle {
  chart: {
    addCandlestickSeries: Mock;
    applyOptions: Mock;
    remove: Mock;
    timeScale: Mock;
    subscribeCrosshairMove: Mock;
    unsubscribeCrosshairMove: Mock;
  };
  series: { setData: Mock; update: Mock };
  timeScale: { fitContent: Mock };
  /** The latest registered crosshair handler. ``null`` until the
   *  component subscribes during mount. */
  getCrosshairHandler: () => CrosshairHandler | null;
}

function makeFakeChartBundle(): FakeChartBundle {
  const setData = vi.fn();
  const update = vi.fn();
  const series = { setData, update };
  const addCandlestickSeries = vi.fn(() => series);
  const applyOptions = vi.fn();
  const remove = vi.fn();
  const fitContent = vi.fn();
  const timeScale = { fitContent };
  const timeScaleFn = vi.fn(() => timeScale);
  let crosshairHandler: CrosshairHandler | null = null;
  const subscribeCrosshairMove = vi.fn((h: CrosshairHandler) => {
    crosshairHandler = h;
  });
  const unsubscribeCrosshairMove = vi.fn(() => {
    crosshairHandler = null;
  });
  return {
    chart: {
      addCandlestickSeries,
      applyOptions,
      remove,
      timeScale: timeScaleFn,
      subscribeCrosshairMove,
      unsubscribeCrosshairMove,
    },
    series,
    timeScale,
    getCrosshairHandler: () => crosshairHandler,
  };
}

// ─── Capturing ResizeObserver ─────────────────────────────────────────

interface FakeObserver {
  callback: ResizeObserverCallback;
  observe: Mock;
  unobserve: Mock;
  disconnect: Mock;
}

const observerInstances: FakeObserver[] = [];

// Constructor must be a real function so ``new`` works. We track every
// instance so tests can assert observe / disconnect calls and fire
// the captured callback manually (jsdom ships no real ResizeObserver
// behaviour).
class CapturingResizeObserver implements FakeObserver {
  callback: ResizeObserverCallback;
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  constructor(cb: ResizeObserverCallback) {
    this.callback = cb;
    observerInstances.push(this);
  }
}

const originalResizeObserver = globalThis.ResizeObserver;

// ─── Test fixtures ────────────────────────────────────────────────────

const sampleCandle = (time: number): Candle => ({
  time,
  open: time,
  high: time + 1,
  low: time - 1,
  close: time + 0.5,
});

let bundle: FakeChartBundle;
let createChartFn: Mock;

beforeEach(() => {
  observerInstances.length = 0;
  globalThis.ResizeObserver =
    CapturingResizeObserver as unknown as typeof ResizeObserver;
  bundle = makeFakeChartBundle();
  // Always returns the SAME bundle within a test so assertions on
  // ``bundle.chart.applyOptions`` / ``bundle.series.setData`` work
  // even after re-renders that don't recreate the chart.
  createChartFn = vi.fn(() => bundle.chart);
});

afterEach(() => {
  globalThis.ResizeObserver = originalResizeObserver;
  vi.clearAllMocks();
});

// ─── Mount ────────────────────────────────────────────────────────────

describe("CandlestickChart — mount", () => {
  it("calls createChartFn with the container + width/height + dark theme", () => {
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(createChartFn).toHaveBeenCalledTimes(1);
    const [container, options] = createChartFn.mock.calls[0];
    expect(container).toBeInstanceOf(HTMLDivElement);
    expect(options).toEqual(
      expect.objectContaining({
        width: expect.any(Number),
        height: expect.any(Number),
        layout: expect.objectContaining({
          textColor: "#d4d4d4",
          // C10: TradingView attribution overlay disabled.
          attributionLogo: false,
        }),
      }),
    );
  });

  it("calls addCandlestickSeries with the up/down colour config", () => {
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.chart.addCandlestickSeries).toHaveBeenCalledTimes(1);
    const [opts] = bundle.chart.addCandlestickSeries.mock.calls[0];
    expect(opts).toMatchObject({
      upColor: "#22c55e",
      downColor: "#ef4444",
    });
  });

  it("constructs a ResizeObserver and observes the container", () => {
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(observerInstances).toHaveLength(1);
    const observer = observerInstances[0];
    expect(observer.observe).toHaveBeenCalledTimes(1);
    const [observed] = observer.observe.mock.calls[0];
    expect(observed).toBeInstanceOf(HTMLDivElement);
  });
});

// ─── R1 — Resize ──────────────────────────────────────────────────────

describe("CandlestickChart — R1 resize", () => {
  it("firing the observer callback triggers chart.applyOptions with the new rect", () => {
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    const observer = observerInstances[0];
    observer.callback(
      [
        {
          contentRect: { width: 800, height: 600 },
        } as unknown as ResizeObserverEntry,
      ],
      observer as unknown as ResizeObserver,
    );

    expect(bundle.chart.applyOptions).toHaveBeenCalledWith({
      width: 800,
      height: 600,
    });
  });

  it("ignores resize entries with no ResizeObserverEntry", () => {
    // Defensive: the component guards on ``entries[0]`` being truthy.
    // An empty entries array should be a no-op, not a crash.
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    const observer = observerInstances[0];
    expect(() =>
      observer.callback([], observer as unknown as ResizeObserver),
    ).not.toThrow();
    expect(bundle.chart.applyOptions).not.toHaveBeenCalled();
  });
});

// ─── Data sync ────────────────────────────────────────────────────────

describe("CandlestickChart — data sync", () => {
  it("first paint with candles calls series.setData with the full mapped array", () => {
    render(
      <CandlestickChart
        candles={[sampleCandle(1), sampleCandle(2)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.series.setData).toHaveBeenCalledTimes(1);
    const [arr] = bundle.series.setData.mock.calls[0];
    expect(arr).toHaveLength(2);
    expect(arr[0]).toMatchObject({
      time: 1,
      open: 1,
      high: 2,
      low: 0,
      close: 1.5,
    });
  });

  it("(Phase1) first paint also calls timeScale().fitContent() so the historical preload is visibly rendered", () => {
    // Without fitContent, Lightweight Charts' default visible
    // logical range is barSpacing × container width, and
    // subsequent live ``update`` calls auto-pan the right edge —
    // together those silently push the historical preload off
    // narrow viewports. Phase-1 regression guard.
    render(
      <CandlestickChart
        candles={[sampleCandle(1), sampleCandle(2), sampleCandle(3)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.chart.timeScale).toHaveBeenCalledTimes(1);
    expect(bundle.timeScale.fitContent).toHaveBeenCalledTimes(1);
  });

  it("(Phase1) tail-only update path does NOT call fitContent (preserves user pan/zoom)", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[sampleCandle(1), sampleCandle(2)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.timeScale.fitContent.mockClear();

    rerender(
      <CandlestickChart
        candles={[sampleCandle(1), sampleCandle(2), sampleCandle(3)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.timeScale.fitContent).not.toHaveBeenCalled();
  });

  it("tail-forward update routes through series.update (O(1) path)", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[sampleCandle(1), sampleCandle(2)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    // setData fired on first paint — clear so the next assertion sees
    // only the tail-only update path.
    bundle.series.setData.mockClear();

    rerender(
      <CandlestickChart
        candles={[sampleCandle(1), sampleCandle(2), sampleCandle(3)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.series.setData).not.toHaveBeenCalled();
    expect(bundle.series.update).toHaveBeenCalledTimes(1);
    expect(bundle.series.update).toHaveBeenCalledWith(
      expect.objectContaining({ time: 3 }),
    );
  });

  it("tail-backward (symbol switch) falls back to series.setData + re-fits", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[sampleCandle(10), sampleCandle(20)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.series.setData.mockClear();
    bundle.timeScale.fitContent.mockClear();

    // New (symbol, timeframe) ships a fully new candle array whose
    // tail.time is < the previous tail. The component must fall back
    // to setData rather than try to ``update`` backwards.
    rerender(
      <CandlestickChart
        candles={[sampleCandle(1), sampleCandle(2)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.series.setData).toHaveBeenCalledTimes(1);
    const [arr] = bundle.series.setData.mock.calls[0];
    expect(arr.map((c: { time: number }) => c.time)).toEqual([1, 2]);
    // The prior fit's logical range no longer maps to anything
    // sensible after a symbol/timeframe switch; re-fit is required.
    expect(bundle.timeScale.fitContent).toHaveBeenCalledTimes(1);
  });

  it("empty candles call setData([]) and reset the lastCandleTime", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[sampleCandle(1), sampleCandle(2)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.series.setData.mockClear();

    rerender(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.series.setData).toHaveBeenCalledWith([]);

    // After reset, a fresh first-paint should setData full array
    // again (not try to ``update`` against a stale lastCandleTimeRef).
    bundle.series.setData.mockClear();
    rerender(
      <CandlestickChart
        candles={[sampleCandle(5)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    expect(bundle.series.setData).toHaveBeenCalledTimes(1);
    expect(bundle.series.update).not.toHaveBeenCalled();
  });

  it("same-time update (intra-bar tick) routes through series.update", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[sampleCandle(1), sampleCandle(2)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.series.setData.mockClear();

    // Tail time UNCHANGED (still 2) but body updates — intra-bar tick
    // case. Routes through update (Lightweight Charts replaces the
    // tail when ``time`` matches).
    const updatedTail: Candle = {
      time: 2,
      open: 2,
      high: 99, // mid-bar high spike
      low: 1,
      close: 50,
    };
    rerender(
      <CandlestickChart
        candles={[sampleCandle(1), updatedTail]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.series.update).toHaveBeenCalledWith(
      expect.objectContaining({ time: 2, high: 99, close: 50 }),
    );
  });
});

// ─── Unmount ──────────────────────────────────────────────────────────

describe("CandlestickChart — unmount", () => {
  it("disconnects the observer and removes the chart", () => {
    const { unmount } = render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    const observer = observerInstances[0];
    unmount();

    expect(observer.disconnect).toHaveBeenCalledTimes(1);
    expect(bundle.chart.remove).toHaveBeenCalledTimes(1);
  });

  it("does not leak when chart.remove throws", () => {
    bundle.chart.remove.mockImplementation(() => {
      throw new Error("remove blew up");
    });

    const { unmount } = render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    // The component wraps remove in try/catch — unmount must complete
    // cleanly so React doesn't enter an inconsistent state.
    expect(() => unmount()).not.toThrow();
    expect(bundle.chart.remove).toHaveBeenCalledTimes(1);
  });

  it("(Phase2) unsubscribes the crosshair handler", () => {
    const { unmount } = render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    expect(bundle.chart.subscribeCrosshairMove).toHaveBeenCalledTimes(1);
    unmount();
    expect(bundle.chart.unsubscribeCrosshairMove).toHaveBeenCalledTimes(1);
  });
});

// ─── Phase 2 — Crosshair OHLCV tooltip ─────────────────────────────────

describe("CandlestickChart — Phase2 crosshair tooltip", () => {
  // Convenience: build a candle with realistic OHLCV that the tooltip
  // can format. Use a Jan-2026 epoch (deterministic — no Date.now()).
  const ts = Math.floor(Date.UTC(2026, 0, 15, 9, 30, 0) / 1000);
  const niftyCandle = (timeOffset: number, isUp = true): Candle => ({
    symbol: "NIFTY",
    timeframe: "5m",
    time: ts + timeOffset,
    open: 22500.5,
    high: 22550.25,
    low: 22480.0,
    close: isUp ? 22540.75 : 22460.0,
    volume: 1_234_567,
  });

  it("subscribes to subscribeCrosshairMove on mount", () => {
    render(
      <CandlestickChart
        candles={[niftyCandle(0)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.chart.subscribeCrosshairMove).toHaveBeenCalledTimes(1);
    expect(bundle.getCrosshairHandler()).toBeInstanceOf(Function);
  });

  it("renders the tooltip with OHLCV when the crosshair hovers a known candle", () => {
    const candles = [
      niftyCandle(0, true),
      niftyCandle(300, true),
      niftyCandle(600, true),
    ];
    render(
      <CandlestickChart
        candles={candles}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    const handler = bundle.getCrosshairHandler();
    expect(handler).not.toBeNull();
    act(() => {
      handler!({ point: { x: 200, y: 100 }, time: candles[1].time });
    });

    const tooltip = screen.getByTestId("chart-tooltip");
    expect(tooltip).toBeInTheDocument();
    expect(tooltip).toHaveAttribute("data-direction", "up");
    expect(screen.getByTestId("tt-open")).toHaveTextContent("22,500.50");
    expect(screen.getByTestId("tt-high")).toHaveTextContent("22,550.25");
    expect(screen.getByTestId("tt-low")).toHaveTextContent("22,480.00");
    expect(screen.getByTestId("tt-close")).toHaveTextContent("22,540.75");
    // 1,234,567 → 12.35L (Indian short-form: 1L = 100,000)
    expect(screen.getByTestId("tt-volume")).toHaveTextContent("12.35L");
  });

  it("flags down-direction tooltips with data-direction='down' (red close)", () => {
    const candles = [niftyCandle(0, false)];
    render(
      <CandlestickChart
        candles={candles}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    act(() => {
      bundle.getCrosshairHandler()!({
        point: { x: 50, y: 50 },
        time: candles[0].time,
      });
    });

    expect(screen.getByTestId("chart-tooltip")).toHaveAttribute(
      "data-direction",
      "down",
    );
  });

  it("hides the tooltip when the crosshair leaves the chart (point=undefined)", () => {
    const candles = [niftyCandle(0)];
    render(
      <CandlestickChart
        candles={candles}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    const handler = bundle.getCrosshairHandler()!;
    act(() => {
      handler({ point: { x: 50, y: 50 }, time: candles[0].time });
    });
    expect(screen.queryByTestId("chart-tooltip")).toBeInTheDocument();

    act(() => {
      handler({}); // crosshair leave: point + time both undefined
    });
    expect(screen.queryByTestId("chart-tooltip")).toBeNull();
  });

  it("hides the tooltip when the hovered time has no matching candle", () => {
    const candles = [niftyCandle(0), niftyCandle(300)];
    render(
      <CandlestickChart
        candles={candles}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    const handler = bundle.getCrosshairHandler()!;
    // First show the tooltip
    act(() => {
      handler({ point: { x: 50, y: 50 }, time: candles[0].time });
    });
    expect(screen.queryByTestId("chart-tooltip")).toBeInTheDocument();
    // Then hover at a time that's not in the candle array
    act(() => {
      handler({ point: { x: 75, y: 50 }, time: candles[0].time + 7 });
    });
    expect(screen.queryByTestId("chart-tooltip")).toBeNull();
  });

  it("survives a hover on an empty candles array (no crash)", () => {
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    const handler = bundle.getCrosshairHandler()!;
    expect(() =>
      act(() => {
        handler({ point: { x: 50, y: 50 }, time: 999_999 });
      }),
    ).not.toThrow();
    expect(screen.queryByTestId("chart-tooltip")).toBeNull();
  });

  it("hover updates after a candle prop change reflect the new candle (ref-mirror)", () => {
    // Phase-2 perf contract: the handler is created once at mount
    // and reads candles from a ref so prop changes don't churn
    // subscribe/unsubscribe. Test the contract by re-rendering with
    // a new candle list and asserting the handler still resolves.
    const initial = [niftyCandle(0)];
    const { rerender } = render(
      <CandlestickChart
        candles={initial}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.chart.subscribeCrosshairMove).toHaveBeenCalledTimes(1);

    const next = [...initial, niftyCandle(300)];
    rerender(
      <CandlestickChart
        candles={next}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    // No additional subscribe calls — the handler is reused.
    expect(bundle.chart.subscribeCrosshairMove).toHaveBeenCalledTimes(1);

    act(() => {
      bundle.getCrosshairHandler()!({
        point: { x: 100, y: 50 },
        time: next[1].time,
      });
    });
    // The newly-added candle is resolvable by the existing handler.
    expect(screen.getByTestId("chart-tooltip")).toBeInTheDocument();
  });
});

// ─── Phase 2 — ChartTooltip presentational sub-component ───────────────

describe("ChartTooltip — presentational", () => {
  // ChartTooltip is exported so we can render it in isolation without
  // having to drive a Lightweight Charts mock.
  const baseCandle: Candle = {
    symbol: "NIFTY",
    timeframe: "5m",
    time: Math.floor(Date.UTC(2026, 0, 15, 9, 30, 0) / 1000),
    open: 22_500,
    high: 22_550,
    low: 22_480,
    close: 22_540,
    volume: 5_000,
  };

  it("renders all OHLCV labels and a formatted timestamp", () => {
    render(<ChartTooltip candle={baseCandle} left={0} top={0} />);

    expect(screen.getByTestId("tt-open")).toBeInTheDocument();
    expect(screen.getByTestId("tt-high")).toBeInTheDocument();
    expect(screen.getByTestId("tt-low")).toBeInTheDocument();
    expect(screen.getByTestId("tt-close")).toBeInTheDocument();
    expect(screen.getByTestId("tt-volume")).toBeInTheDocument();
  });

  it("formats sub-1K volume with thousands separator (no abbreviation)", () => {
    render(
      <ChartTooltip
        candle={{ ...baseCandle, volume: 950 }}
        left={0}
        top={0}
      />,
    );
    // 950 is below the 1K threshold — locale-formatted as-is.
    expect(screen.getByTestId("tt-volume")).toHaveTextContent("950");
  });

  it("uses Crore (Cr) suffix for volume ≥ 1 crore", () => {
    render(
      <ChartTooltip
        candle={{ ...baseCandle, volume: 25_000_000 }}
        left={0}
        top={0}
      />,
    );
    expect(screen.getByTestId("tt-volume")).toHaveTextContent("2.50Cr");
  });

  it("uses Thousand (K) suffix for 1K ≤ volume < 1L", () => {
    render(
      <ChartTooltip
        candle={{ ...baseCandle, volume: 95_000 }}
        left={0}
        top={0}
      />,
    );
    expect(screen.getByTestId("tt-volume")).toHaveTextContent("95.0K");
  });

  it("treats undefined volume as 0", () => {
    const noVol = { ...baseCandle } as unknown as Record<string, unknown>;
    delete noVol.volume;
    render(
      <ChartTooltip
        candle={noVol as unknown as Candle}
        left={0}
        top={0}
      />,
    );
    expect(screen.getByTestId("tt-volume")).toHaveTextContent("0");
  });

  it("applies the supplied left/top inline styles", () => {
    render(<ChartTooltip candle={baseCandle} left={42} top={84} />);
    const tt = screen.getByTestId("chart-tooltip");
    expect(tt).toHaveStyle({ left: "42px", top: "84px" });
  });
});
