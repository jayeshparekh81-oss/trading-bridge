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

import { render } from "@testing-library/react";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";

import { CandlestickChart } from "@/components/chart/CandlestickChart";
import type { Candle } from "@/lib/chart/types";

// ─── Fake Lightweight Charts factory ──────────────────────────────────

interface FakeChartBundle {
  chart: {
    addCandlestickSeries: Mock;
    applyOptions: Mock;
    remove: Mock;
  };
  series: { setData: Mock; update: Mock };
}

function makeFakeChartBundle(): FakeChartBundle {
  const setData = vi.fn();
  const update = vi.fn();
  const series = { setData, update };
  const addCandlestickSeries = vi.fn(() => series);
  const applyOptions = vi.fn();
  const remove = vi.fn();
  return {
    chart: { addCandlestickSeries, applyOptions, remove },
    series,
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

  it("tail-backward (symbol switch) falls back to series.setData", () => {
    const { rerender } = render(
      <CandlestickChart
        candles={[sampleCandle(10), sampleCandle(20)]}
        createChartFn={createChartFn as unknown as typeof createChartFn}
      />,
    );
    bundle.series.setData.mockClear();

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
});
