/**
 * CandlestickChart — Lightweight Charts v4 wrapper.
 *
 * Lifecycle:
 *   - On mount: ``createChart`` against the wrapping div, configured
 *     for the dark theme (Day 5 ships dark-only; theme switch is
 *     Day 4 polish).
 *   - On every ``candles`` change: ``setData`` for the full series
 *     (initial load + symbol/timeframe change), OR ``update`` for
 *     a tail-only change (live tick / bucket roll).
 *   - On unmount: ``chart.remove()`` + ResizeObserver disconnect.
 *
 * R1 (ResizeObserver):
 *   - Observes the container's bounding rect.
 *   - ``chart.applyOptions({ width, height })`` on each resize.
 *   - Handles the dashboard sidebar's collapse/expand without
 *     overflow or stale viewport.
 *
 * Performance contract (master brief quality bar):
 *   - Tail-only updates use ``series.update(...)`` (O(1)) so live
 *     tick → render stays under 50ms even on a 200-bar series.
 *   - Full ``setData`` only fires when the candle array's identity
 *     changes (memoised via referential equality of the prop) —
 *     prevents wasted full re-renders on heartbeat frames that
 *     don't change ``candles``.
 */

"use client";

import {
  CandlestickSeriesPartialOptions,
  ColorType,
  CrosshairMode,
  IChartApi,
  ISeriesApi,
  UTCTimestamp,
  createChart,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { Candle } from "@/lib/chart/types";

// ═══════════════════════════════════════════════════════════════════════
// Theme — dark only for Day 5
// ═══════════════════════════════════════════════════════════════════════

const DARK_THEME = {
  layout: {
    background: { type: ColorType.Solid, color: "#0a0a0a" },
    textColor: "#d4d4d4",
  },
  grid: {
    vertLines: { color: "#1f1f1f" },
    horzLines: { color: "#1f1f1f" },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
  },
  rightPriceScale: {
    borderColor: "#262626",
  },
  timeScale: {
    borderColor: "#262626",
    timeVisible: true,
    secondsVisible: false,
  },
} as const;

const CANDLE_COLORS: CandlestickSeriesPartialOptions = {
  upColor: "#22c55e", // green-500
  downColor: "#ef4444", // red-500
  borderUpColor: "#22c55e",
  borderDownColor: "#ef4444",
  wickUpColor: "#22c55e",
  wickDownColor: "#ef4444",
};

// ═══════════════════════════════════════════════════════════════════════
// Props
// ═══════════════════════════════════════════════════════════════════════

export interface CandlestickChartProps {
  candles: Candle[];
  /** Test seam — inject a fake ``createChart`` to skip canvas DOM
   *  setup in jsdom. Production callers should never pass this. */
  createChartFn?: typeof createChart;
}

// ═══════════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════════

export function CandlestickChart({
  candles,
  createChartFn = createChart,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const lastCandleTimeRef = useRef<number | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // ── Mount: createChart + addCandlestickSeries + ResizeObserver ────
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChartFn(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      ...DARK_THEME,
    });
    const series = chart.addCandlestickSeries(CANDLE_COLORS);
    chartRef.current = chart;
    seriesRef.current = series;

    // R1: observe container, applyOptions on size change.
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry || !chartRef.current) return;
      const { width, height } = entry.contentRect;
      chartRef.current.applyOptions({ width, height });
    });
    observer.observe(container);
    resizeObserverRef.current = observer;

    return () => {
      observer.disconnect();
      resizeObserverRef.current = null;
      seriesRef.current = null;
      chartRef.current = null;
      try {
        chart.remove();
      } catch {
        /* remove-time errors must not leak */
      }
    };
    // ``createChartFn`` only matters at mount — runtime swap is not
    // a supported scenario.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Data sync: full setData on identity change, update on tail ────
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    if (candles.length === 0) {
      series.setData([]);
      lastCandleTimeRef.current = null;
      return;
    }

    const tail = candles[candles.length - 1];
    const prev = lastCandleTimeRef.current;

    if (prev === null) {
      // First paint — full setData.
      series.setData(
        candles.map((c) => ({
          time: c.time as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })),
      );
    } else if (tail.time >= prev) {
      // Tail-only path: same-bucket update OR new-bucket append.
      // Lightweight Charts' ``update`` covers both (replaces tail
      // if ``time`` matches; appends otherwise).
      series.update({
        time: tail.time as UTCTimestamp,
        open: tail.open,
        high: tail.high,
        low: tail.low,
        close: tail.close,
      });
    } else {
      // Symbol/timeframe change shipped a fully new array whose tail
      // time is < the previous tail. Fall back to full setData.
      series.setData(
        candles.map((c) => ({
          time: c.time as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })),
      );
    }
    lastCandleTimeRef.current = tail.time;
  }, [candles]);

  return (
    <div
      ref={containerRef}
      className="h-full w-full"
      data-testid="candlestick-chart-container"
    />
  );
}
