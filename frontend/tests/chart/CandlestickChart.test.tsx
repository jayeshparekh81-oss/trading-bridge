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

type LogicalRangeHandler = (range: { from: number; to: number } | null) => void;

type ClickHandler = (param: {
  point?: { x: number; y: number };
  time?: number;
  hoveredObjectId?: string;
}) => void;

interface FakeChartBundle {
  chart: {
    addCandlestickSeries: Mock;
    addHistogramSeries: Mock;
    applyOptions: Mock;
    remove: Mock;
    timeScale: Mock;
    subscribeCrosshairMove: Mock;
    unsubscribeCrosshairMove: Mock;
    subscribeClick: Mock;
    unsubscribeClick: Mock;
  };
  series: {
    setData: Mock;
    update: Mock;
    priceScale: Mock;
    setMarkers: Mock;
  };
  /** Phase 3 — volume histogram. ``null`` until the component
   *  lazy-creates it on the first candles array with positive
   *  volume. */
  volumeSeries: {
    setData: Mock;
    update: Mock;
    priceScale: Mock;
  };
  priceScale: { applyOptions: Mock };
  volumePriceScale: { applyOptions: Mock };
  timeScale: {
    fitContent: Mock;
    subscribeVisibleLogicalRangeChange: Mock;
    unsubscribeVisibleLogicalRangeChange: Mock;
    getVisibleRange: Mock;
    setVisibleRange: Mock;
  };
  /** The latest registered crosshair handler. ``null`` until the
   *  component subscribes during mount. */
  getCrosshairHandler: () => CrosshairHandler | null;
  /** Phase 5 — the latest registered visible-logical-range handler. */
  getLogicalRangeHandler: () => LogicalRangeHandler | null;
  /** Day 3 / Phase 1 — the latest registered click handler. */
  getClickHandler: () => ClickHandler | null;
}

function makeFakeChartBundle(): FakeChartBundle {
  // ── Price (candlestick) series + its own price scale ──────────
  const priceScaleApplyOptions = vi.fn();
  const priceScale = { applyOptions: priceScaleApplyOptions };
  const setData = vi.fn();
  const update = vi.fn();
  const setMarkers = vi.fn();
  const seriesPriceScaleFn = vi.fn(() => priceScale);
  const series = {
    setData,
    update,
    setMarkers,
    priceScale: seriesPriceScaleFn,
  };
  const addCandlestickSeries = vi.fn(() => series);

  // ── Volume (histogram) series + its own price scale ───────────
  const volumePriceScaleApplyOptions = vi.fn();
  const volumePriceScale = {
    applyOptions: volumePriceScaleApplyOptions,
  };
  const volumeSetData = vi.fn();
  const volumeUpdate = vi.fn();
  const volumePriceScaleFn = vi.fn(() => volumePriceScale);
  const volumeSeries = {
    setData: volumeSetData,
    update: volumeUpdate,
    priceScale: volumePriceScaleFn,
  };
  const addHistogramSeries = vi.fn(() => volumeSeries);

  const applyOptions = vi.fn();
  const remove = vi.fn();
  const fitContent = vi.fn();
  const getVisibleRange = vi.fn(() => ({ from: 0, to: 1_000_000_000 }));
  const setVisibleRange = vi.fn();
  let logicalRangeHandler: LogicalRangeHandler | null = null;
  const subscribeVisibleLogicalRangeChange = vi.fn(
    (h: LogicalRangeHandler) => {
      logicalRangeHandler = h;
    },
  );
  const unsubscribeVisibleLogicalRangeChange = vi.fn(() => {
    logicalRangeHandler = null;
  });
  const timeScale = {
    fitContent,
    subscribeVisibleLogicalRangeChange,
    unsubscribeVisibleLogicalRangeChange,
    getVisibleRange,
    setVisibleRange,
  };
  const timeScaleFn = vi.fn(() => timeScale);
  let crosshairHandler: CrosshairHandler | null = null;
  const subscribeCrosshairMove = vi.fn((h: CrosshairHandler) => {
    crosshairHandler = h;
  });
  const unsubscribeCrosshairMove = vi.fn(() => {
    crosshairHandler = null;
  });
  let clickHandler: ClickHandler | null = null;
  const subscribeClick = vi.fn((h: ClickHandler) => {
    clickHandler = h;
  });
  const unsubscribeClick = vi.fn(() => {
    clickHandler = null;
  });
  return {
    chart: {
      addCandlestickSeries,
      addHistogramSeries,
      applyOptions,
      remove,
      timeScale: timeScaleFn,
      subscribeCrosshairMove,
      unsubscribeCrosshairMove,
      subscribeClick,
      unsubscribeClick,
    },
    series,
    volumeSeries,
    priceScale,
    volumePriceScale,
    timeScale,
    getCrosshairHandler: () => crosshairHandler,
    getLogicalRangeHandler: () => logicalRangeHandler,
    getClickHandler: () => clickHandler,
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
let warnSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  observerInstances.length = 0;
  globalThis.ResizeObserver =
    CapturingResizeObserver as unknown as typeof ResizeObserver;
  // Phase 3: the data-sync effect emits a console.warn when candles
  // arrive without volume (some option chains, certain MCX symbols).
  // Most existing tests use the volume-less sampleCandle helper, so
  // silence by default and let the dedicated skip test inspect the
  // spy explicitly.
  warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
  bundle = makeFakeChartBundle();
  // Always returns the SAME bundle within a test so assertions on
  // ``bundle.chart.applyOptions`` / ``bundle.series.setData`` work
  // even after re-renders that don't recreate the chart.
  createChartFn = vi.fn(() => bundle.chart);
});

afterEach(() => {
  globalThis.ResizeObserver = originalResizeObserver;
  warnSpy.mockRestore();
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

    // ``chart.timeScale()`` is called both during mount (Phase 5
    // subscribeVisibleLogicalRangeChange) and during the data-sync
    // effect (fitContent) — so its raw call count is implementation-
    // detail noise. The relevant assertion is that fitContent itself
    // fires exactly once.
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

// ─── Phase 3 — Volume bars pane ────────────────────────────────────────

describe("CandlestickChart — Phase3 volume pane", () => {
  // Helper that includes a positive volume so the volume series is
  // lazy-created. ``isUp`` controls the close-vs-open direction so
  // tests can assert per-bar histogram colour.
  const candleWithVol = (
    time: number,
    isUp = true,
    volume = 1_000,
  ): Candle => ({
    symbol: "NIFTY",
    timeframe: "5m",
    time,
    open: 100,
    high: 105,
    low: 95,
    close: isUp ? 104 : 96,
    volume,
  });

  it("does NOT add a histogram series on mount (lazy creation)", () => {
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    // Mount alone (no candles) must not create the volume series —
    // saves DOM/canvas overhead for symbols that never carry volume.
    expect(bundle.chart.addHistogramSeries).not.toHaveBeenCalled();
  });

  it("re-applies price-series scaleMargins on mount so the canvas reserves the volume strip", () => {
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.priceScale.applyOptions).toHaveBeenCalledWith({
      scaleMargins: { top: 0.05, bottom: 0.27 },
    });
  });

  it("lazy-creates the histogram series on the first paint with positive volume", () => {
    render(
      <CandlestickChart
        candles={[candleWithVol(1), candleWithVol(2)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.chart.addHistogramSeries).toHaveBeenCalledTimes(1);
    const [opts] = bundle.chart.addHistogramSeries.mock.calls[0];
    expect(opts).toMatchObject({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    // Volume scale margins push the histogram pane into the bottom
    // ~25% of the chart canvas.
    expect(bundle.volumePriceScale.applyOptions).toHaveBeenCalledWith({
      scaleMargins: { top: 0.75, bottom: 0 },
    });
  });

  it("first paint setData on the volume series carries per-bar up/down colour", () => {
    render(
      <CandlestickChart
        candles={[
          candleWithVol(1, true), // green
          candleWithVol(2, false), // red
          candleWithVol(3, true), // green
        ]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.volumeSeries.setData).toHaveBeenCalledTimes(1);
    const [arr] = bundle.volumeSeries.setData.mock.calls[0];
    expect(arr).toHaveLength(3);
    expect(arr[0].color).toBe("rgba(34, 197, 94, 0.55)"); // green-500
    expect(arr[1].color).toBe("rgba(239, 68, 68, 0.55)"); // red-500
    expect(arr[2].color).toBe("rgba(34, 197, 94, 0.55)"); // green-500
    // Each entry carries the candle's volume verbatim.
    for (const entry of arr) {
      expect(entry.value).toBe(1_000);
    }
  });

  it("tail-only update path also calls volumeSeries.update with the new bar", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[candleWithVol(1, true), candleWithVol(2, true)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.volumeSeries.setData.mockClear();
    bundle.volumeSeries.update.mockClear();

    rerender(
      <CandlestickChart
        candles={[
          candleWithVol(1, true),
          candleWithVol(2, true),
          candleWithVol(3, false, 2_500),
        ]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.volumeSeries.update).toHaveBeenCalledTimes(1);
    expect(bundle.volumeSeries.setData).not.toHaveBeenCalled();
    const [bar] = bundle.volumeSeries.update.mock.calls[0];
    expect(bar).toMatchObject({
      time: 3,
      value: 2_500,
      color: "rgba(239, 68, 68, 0.55)",
    });
  });

  it("symbol/timeframe switch (tail-backward) re-fires volumeSeries.setData with the new array", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[candleWithVol(10, true), candleWithVol(20, true)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.volumeSeries.setData.mockClear();

    rerender(
      <CandlestickChart
        candles={[candleWithVol(1, false), candleWithVol(2, true)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.volumeSeries.setData).toHaveBeenCalledTimes(1);
    const [arr] = bundle.volumeSeries.setData.mock.calls[0];
    expect(arr.map((e: { time: number }) => e.time)).toEqual([1, 2]);
  });

  it("empty candles call volumeSeries.setData([]) so the pane clears in lockstep with price", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[candleWithVol(1, true), candleWithVol(2, true)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.volumeSeries.setData.mockClear();

    rerender(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.volumeSeries.setData).toHaveBeenCalledWith([]);
  });

  it("gracefully skips the volume series when candles carry no positive volume — logs a warning", () => {
    // Volume-less feed (e.g. an MCX option chain with no V tape).
    const noVol = (time: number): Candle => ({
      symbol: "NIFTY",
      timeframe: "5m",
      time,
      open: 100,
      high: 101,
      low: 99,
      close: 100.5,
      volume: 0,
    });

    render(
      <CandlestickChart
        candles={[noVol(1), noVol(2), noVol(3)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.chart.addHistogramSeries).not.toHaveBeenCalled();
    // The skip is surfaced via console.warn so operators tailing
    // dev-server logs notice silent volume-pane omission.
    expect(warnSpy).toHaveBeenCalledTimes(1);
    expect(warnSpy.mock.calls[0]?.[0]).toMatch(/no positive volume/i);
  });

  it("does NOT log the warn twice — gated to first paint only", () => {
    const noVol = (time: number): Candle => ({
      symbol: "NIFTY",
      timeframe: "5m",
      time,
      open: 100,
      high: 101,
      low: 99,
      close: 100.5,
      volume: 0,
    });

    const { rerender } = render(
      <CandlestickChart
        candles={[noVol(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    expect(warnSpy).toHaveBeenCalledTimes(1);

    rerender(
      <CandlestickChart
        candles={[noVol(1), noVol(2)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    // Same volume-less array on next render → no second warn.
    expect(warnSpy).toHaveBeenCalledTimes(1);
  });
});

// ─── Phase 5 — Scroll-back lazy load ───────────────────────────────────

describe("CandlestickChart — Phase5 scroll-back trigger", () => {
  const candleAt = (time: number): Candle => ({
    symbol: "NIFTY",
    timeframe: "5m",
    time,
    open: 100,
    high: 105,
    low: 95,
    close: 101,
    volume: 100,
  });

  it("subscribes to subscribeVisibleLogicalRangeChange on mount", () => {
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        onRequestOlderHistory={vi.fn()}
      />,
    );

    expect(
      bundle.timeScale.subscribeVisibleLogicalRangeChange,
    ).toHaveBeenCalledTimes(1);
    expect(bundle.getLogicalRangeHandler()).toBeInstanceOf(Function);
  });

  it("unsubscribes the logical-range handler on unmount", () => {
    const { unmount } = render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    unmount();
    expect(
      bundle.timeScale.unsubscribeVisibleLogicalRangeChange,
    ).toHaveBeenCalledTimes(1);
  });

  it("fires onRequestOlderHistory with the leftmost candle's time when range.from < length × 0.2", () => {
    const onRequest = vi.fn();
    const candles = Array.from({ length: 100 }, (_, i) => candleAt(i + 1_000));
    render(
      <CandlestickChart
        candles={candles}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        onRequestOlderHistory={onRequest}
      />,
    );

    // 100 bars × 0.2 = 20 → from=15 triggers, from=25 does not.
    bundle.getLogicalRangeHandler()!({ from: 15, to: 60 });
    expect(onRequest).toHaveBeenCalledWith(candles[0].time);
  });

  it("does NOT fire when range.from is past the trigger threshold", () => {
    const onRequest = vi.fn();
    const candles = Array.from({ length: 100 }, (_, i) => candleAt(i + 1_000));
    render(
      <CandlestickChart
        candles={candles}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        onRequestOlderHistory={onRequest}
      />,
    );

    bundle.getLogicalRangeHandler()!({ from: 25, to: 75 });
    expect(onRequest).not.toHaveBeenCalled();
  });

  it("ignores null range (chart not yet rendered)", () => {
    const onRequest = vi.fn();
    render(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        onRequestOlderHistory={onRequest}
      />,
    );

    expect(() => bundle.getLogicalRangeHandler()!(null)).not.toThrow();
    expect(onRequest).not.toHaveBeenCalled();
  });

  it("ignores fires when the candles array is empty (defensive)", () => {
    const onRequest = vi.fn();
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        onRequestOlderHistory={onRequest}
      />,
    );

    bundle.getLogicalRangeHandler()!({ from: -5, to: 5 });
    expect(onRequest).not.toHaveBeenCalled();
  });

  it("uses the LATEST onRequestOlderHistory across re-renders (ref-mirror)", () => {
    const initial = vi.fn();
    const candles = [candleAt(1), candleAt(2), candleAt(3)];
    const { rerender } = render(
      <CandlestickChart
        candles={candles}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        onRequestOlderHistory={initial}
      />,
    );

    const replacement = vi.fn();
    rerender(
      <CandlestickChart
        candles={candles}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        onRequestOlderHistory={replacement}
      />,
    );

    bundle.getLogicalRangeHandler()!({ from: 0, to: 1 });
    expect(initial).not.toHaveBeenCalled();
    expect(replacement).toHaveBeenCalledTimes(1);
  });
});

describe("CandlestickChart — Phase5 head-changed (older bars prepended)", () => {
  const candleAt = (time: number): Candle => ({
    symbol: "NIFTY",
    timeframe: "5m",
    time,
    open: 100,
    high: 105,
    low: 95,
    close: 101,
    volume: 100,
  });

  it("re-runs setData (NOT update) when the head changes but the tail is stable", () => {
    const initial = [candleAt(100), candleAt(200), candleAt(300)];
    const { rerender } = render(
      <CandlestickChart
        candles={initial}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.series.setData.mockClear();
    bundle.series.update.mockClear();
    bundle.timeScale.fitContent.mockClear();

    // Older bars prepended: head changes from 100 → 50, tail stays
    // at 300.
    const withOlder = [candleAt(50), candleAt(75), ...initial];
    rerender(
      <CandlestickChart
        candles={withOlder}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.series.setData).toHaveBeenCalledTimes(1);
    const [arr] = bundle.series.setData.mock.calls[0];
    expect(arr.map((c: { time: number }) => c.time)).toEqual([
      50, 75, 100, 200, 300,
    ]);
    expect(bundle.series.update).not.toHaveBeenCalled();
    // CRITICAL: do NOT fitContent — that would zoom out and lose
    // the user's scroll position, undoing the very interaction
    // that triggered the prepend.
    expect(bundle.timeScale.fitContent).not.toHaveBeenCalled();
  });

  it("also re-runs the volume series setData with the prepended bars", () => {
    const initial = [candleAt(100), candleAt(200)];
    const { rerender } = render(
      <CandlestickChart
        candles={initial}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.volumeSeries.setData.mockClear();
    bundle.volumeSeries.update.mockClear();

    rerender(
      <CandlestickChart
        candles={[candleAt(50), ...initial]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.volumeSeries.setData).toHaveBeenCalledTimes(1);
    expect(bundle.volumeSeries.update).not.toHaveBeenCalled();
  });

  it("a SIMULTANEOUS head + tail change (rare race) routes through tail-update — head-changed branch is gated by stable tail", () => {
    // Very unlikely in practice (the parent merges older + live in a
    // useMemo, and live ticks change the tail) but worth defining
    // the behaviour explicitly: if both head and tail change in the
    // same render, the tail-update path wins. The next render with
    // a stable tail then routes through the head-changed setData
    // path naturally.
    const initial = [candleAt(100), candleAt(200)];
    const { rerender } = render(
      <CandlestickChart
        candles={initial}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.series.setData.mockClear();
    bundle.series.update.mockClear();

    rerender(
      <CandlestickChart
        candles={[candleAt(50), ...initial, candleAt(300)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );

    expect(bundle.series.update).toHaveBeenCalledTimes(1);
    expect(bundle.series.setData).not.toHaveBeenCalled();
  });
});

describe("CandlestickChart — Phase5 loading overlay", () => {
  it("renders the older-loading spinner when isLoadingOlder=true", () => {
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        isLoadingOlder
      />,
    );

    const overlay = screen.getByTestId("chart-older-loading");
    expect(overlay).toBeInTheDocument();
    expect(overlay).toHaveTextContent(/loading/i);
    expect(
      screen.getByTestId("chart-older-loading-spinner"),
    ).toBeInTheDocument();
  });

  it("does NOT render the spinner when isLoadingOlder is false / unset", () => {
    render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    expect(screen.queryByTestId("chart-older-loading")).toBeNull();
  });
});

// ─── Day 3 / Phase 1 — markers overlay + click handler ────────────────

describe("CandlestickChart — Phase1/Day3 markers overlay", () => {
  function entryMarker(time: number, price = 22500): Candle {
    // Reuse the Candle type's shape since the bundle doesn't import
    // ChartMarker — but we only need the marker for the markers prop,
    // so cast at call-site below.
    return {
      time,
      open: price,
      high: price,
      low: price,
      close: price,
    } as unknown as Candle;
  }

  const candleAt = (time: number): Candle => ({
    symbol: "NIFTY",
    timeframe: "5m",
    time,
    open: 100,
    high: 105,
    low: 95,
    close: 101,
    volume: 100,
  });

  const sampleMarkers = [
    {
      kind: "ENTRY" as const,
      time: 1000,
      price: 22500,
      quantity: 50,
      side: "BUY",
      pnl: null,
      exit_reason: null,
    },
    {
      kind: "TP_HIT" as const,
      time: 2000,
      price: 22580,
      quantity: 50,
      side: "BUY",
      pnl: 4000,
      exit_reason: "target",
    },
    {
      kind: "SL_HIT" as const,
      time: 3000,
      price: 22480,
      quantity: 50,
      side: "BUY",
      pnl: -3500,
      exit_reason: "stop_loss",
    },
    {
      kind: "EXIT" as const,
      time: 4000,
      price: 22510,
      quantity: 50,
      side: "BUY",
      pnl: 500,
      exit_reason: "square_off",
    },
  ];

  it("subscribes to subscribeClick on mount", () => {
    render(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        onMarkerClick={vi.fn()}
      />,
    );
    expect(bundle.chart.subscribeClick).toHaveBeenCalledTimes(1);
    expect(bundle.getClickHandler()).toBeInstanceOf(Function);
  });

  it("unsubscribes the click handler on unmount", () => {
    const { unmount } = render(
      <CandlestickChart
        candles={[]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    unmount();
    expect(bundle.chart.unsubscribeClick).toHaveBeenCalledTimes(1);
  });

  it("calls series.setMarkers with the LWC shape for each ChartMarker kind", () => {
    render(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={sampleMarkers}
      />,
    );

    expect(bundle.series.setMarkers).toHaveBeenCalled();
    const lastCall =
      bundle.series.setMarkers.mock.calls[
        bundle.series.setMarkers.mock.calls.length - 1
      ];
    const arr = lastCall[0];
    expect(arr).toHaveLength(4);
    // ENTRY → arrowUp belowBar green
    expect(arr[0]).toMatchObject({
      time: 1000,
      shape: "arrowUp",
      position: "belowBar",
      color: "#22c55e",
      id: "ENTRY:1000",
    });
    // TP_HIT → circle aboveBar blue
    expect(arr[1]).toMatchObject({
      shape: "circle",
      position: "aboveBar",
      color: "#3b82f6",
      id: "TP_HIT:2000",
    });
    // SL_HIT → arrowDown aboveBar red
    expect(arr[2]).toMatchObject({
      shape: "arrowDown",
      position: "aboveBar",
      color: "#ef4444",
    });
    // EXIT → square aboveBar neutral
    expect(arr[3]).toMatchObject({
      shape: "square",
      position: "aboveBar",
      color: "#737373",
    });
  });

  it("highlighted marker renders with size: 2 (others size: 1)", () => {
    render(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={sampleMarkers}
        highlightedMarkerId="TP_HIT:2000"
      />,
    );

    const lastCall =
      bundle.series.setMarkers.mock.calls[
        bundle.series.setMarkers.mock.calls.length - 1
      ];
    const arr = lastCall[0];
    expect(arr.find((m: { id: string }) => m.id === "TP_HIT:2000").size).toBe(2);
    expect(arr.find((m: { id: string }) => m.id === "ENTRY:1000").size).toBe(1);
  });

  it("empty markers prop calls setMarkers([]) (clears overlay)", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={sampleMarkers}
      />,
    );
    bundle.series.setMarkers.mockClear();
    rerender(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={[]}
      />,
    );
    expect(bundle.series.setMarkers).toHaveBeenCalledWith([]);
  });

  it("undefined markers prop also clears (defensive)", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={sampleMarkers}
      />,
    );
    bundle.series.setMarkers.mockClear();
    rerender(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    expect(bundle.series.setMarkers).toHaveBeenCalledWith([]);
  });

  it("click handler routes the marker id to onMarkerClick when hoveredObjectId is set", () => {
    const onMarkerClick = vi.fn();
    render(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={sampleMarkers}
        onMarkerClick={onMarkerClick}
      />,
    );
    const handler = bundle.getClickHandler()!;
    handler({
      point: { x: 100, y: 100 },
      time: 2000,
      hoveredObjectId: "TP_HIT:2000",
    });
    expect(onMarkerClick).toHaveBeenCalledWith("TP_HIT:2000");
  });

  it("click handler ignores bare-canvas clicks (no hoveredObjectId)", () => {
    const onMarkerClick = vi.fn();
    render(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={sampleMarkers}
        onMarkerClick={onMarkerClick}
      />,
    );
    bundle.getClickHandler()!({ point: { x: 100, y: 100 }, time: 2000 });
    expect(onMarkerClick).not.toHaveBeenCalled();
  });

  it("highlight outside the visible range triggers timeScale.setVisibleRange", () => {
    bundle.timeScale.getVisibleRange.mockReturnValue({ from: 0, to: 500 });
    const { rerender } = render(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={sampleMarkers}
        highlightedMarkerId={null}
      />,
    );
    bundle.timeScale.setVisibleRange.mockClear();
    rerender(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={sampleMarkers}
        highlightedMarkerId="TP_HIT:2000"
      />,
    );
    expect(bundle.timeScale.setVisibleRange).toHaveBeenCalledTimes(1);
    const [arg] = bundle.timeScale.setVisibleRange.mock.calls[0];
    // Centred on the marker time (2000) with the same width (500).
    expect(arg.from).toBeLessThan(2000);
    expect(arg.to).toBeGreaterThan(2000);
  });

  it("highlight already inside the visible range does NOT pan (preserves user view)", () => {
    bundle.timeScale.getVisibleRange.mockReturnValue({ from: 0, to: 5000 });
    const { rerender } = render(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={sampleMarkers}
        highlightedMarkerId={null}
      />,
    );
    bundle.timeScale.setVisibleRange.mockClear();
    rerender(
      <CandlestickChart
        candles={[candleAt(1)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
        markers={sampleMarkers}
        highlightedMarkerId="TP_HIT:2000"
      />,
    );
    expect(bundle.timeScale.setVisibleRange).not.toHaveBeenCalled();
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
