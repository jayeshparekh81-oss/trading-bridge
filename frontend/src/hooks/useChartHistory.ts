/**
 * useChartHistory — load the initial OHLC window for a (symbol,
 * timeframe) pair via ``GET /api/chart/history`` and convert the
 * wire-shape candles into the chart-renderer-ready numeric form.
 *
 * Day-5 contract:
 *   - Always fetch a fixed-size historical window (default last 200
 *     bars of the requested timeframe). Day 6+ may parameterise.
 *   - Returns ``candles`` as a fully-parsed :type:`Candle[]` sorted
 *     ascending by ``time``.
 *   - ``isLoading`` is true on initial fetch and on every (symbol,
 *     timeframe) change.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchChartHistory } from "@/lib/chart/api";
import {
  parseCandle,
  type Candle,
  type Exchange,
  type Timeframe,
} from "@/lib/chart/types";

const DEFAULT_BAR_COUNT = 200;

const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  "1m": 60,
  "3m": 180,
  "5m": 300,
  "15m": 900,
  "30m": 1_800,
  "1h": 3_600,
  "1d": 86_400,
};

export interface UseChartHistoryOptions {
  symbol: string;
  exchange: Exchange;
  timeframe: Timeframe;
  /** How many bars to request. Default 200. */
  barCount?: number;
  /** Skip the fetch entirely. Mostly for tests. */
  enabled?: boolean;
}

export interface UseChartHistoryState {
  candles: Candle[];
  isLoading: boolean;
  error: Error | null;
  /** Manually re-fetch (e.g. on user retry of error state). */
  refetch: () => void;
}

export function useChartHistory(
  opts: UseChartHistoryOptions,
): UseChartHistoryState {
  const {
    symbol,
    exchange,
    timeframe,
    barCount = DEFAULT_BAR_COUNT,
    enabled = true,
  } = opts;

  const [candles, setCandles] = useState<Candle[]>([]);
  const [isLoading, setIsLoading] = useState(enabled);
  const [error, setError] = useState<Error | null>(null);

  const isAlive = useRef(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const tfSeconds = TIMEFRAME_SECONDS[timeframe];
      const now = new Date();
      // Calendar-aware window: ensure lookback always covers at least 7 days
      // to handle weekends/holidays when market is closed and last bars are days old.
      // Capped at 60 days to bound cache cardinality.
      const tfWindowMs = tfSeconds * barCount * 1000;
      const minWindowMs = 7 * 86400 * 1000; // 7 days
      const maxWindowMs = 60 * 86400 * 1000; // 60 days
      const windowMs = Math.min(Math.max(tfWindowMs, minWindowMs), maxWindowMs);
      const from = new Date(now.getTime() - windowMs);
      const resp = await fetchChartHistory({
        symbol,
        exchange,
        timeframe,
        from: from.toISOString(),
        to: now.toISOString(),
      });
      if (!isAlive.current) return;
      const parsed = resp.candles
        .map(parseCandle)
        .sort((a, b) => a.time - b.time);
      setCandles(parsed);
    } catch (err) {
      if (!isAlive.current) return;
      setError(
        err instanceof Error ? err : new Error("history fetch failed"),
      );
    } finally {
      if (isAlive.current) setIsLoading(false);
    }
  }, [symbol, exchange, timeframe, barCount]);

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }
    isAlive.current = true;
    void load();
    return () => {
      isAlive.current = false;
    };
  }, [enabled, load]);

  return { candles, isLoading, error, refetch: load };
}
