/**
 * useChartScrollback — Phase 5 hook that owns the older-history
 * lazy-load state machine.
 *
 * Responsibilities
 *   1. Buffer ``olderCandles`` (already-prepended bars from prior
 *      fetches). The merged view consumed by the chart is
 *      ``[...olderCandles, ...currentCandles]``.
 *   2. Expose ``requestOlder(beforeEpochSeconds)`` — idempotent
 *      gating on ``isLoadingOlder`` and ``hasReachedCap`` ensures
 *      one-fetch-at-a-time even when the chart fires the trigger
 *      rapidly during fast left-scroll.
 *   3. Reset the buffer on (symbol, timeframe, exchange) changes —
 *      a different symbol's older bars would be nonsensical to
 *      keep around.
 *   4. Enforce the 5-year cap for intraday timeframes (Dhan API
 *      limit, mirrored by the backend) — once the cumulative
 *      scroll-back exceeds the cap, ``hasReachedCap`` flips and
 *      further requests are rejected.
 *
 * The hook is REST-only — it does not touch the WebSocket lifecycle.
 * The WS hook's seed-reset logic compares ``initialCandles`` by
 * reference; the merged-candles assembly happens in the consumer
 * (ChartContainer) so the WS reducer's tail-update path stays the
 * authoritative source for live ticks.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchOlderHistory } from "@/lib/chart/api";
import {
  parseCandle,
  type Candle,
  type Exchange,
  type Timeframe,
} from "@/lib/chart/types";

const FIVE_YEARS_SECONDS = 5 * 365 * 24 * 60 * 60;

const INTRADAY_TIMEFRAMES: ReadonlySet<Timeframe> = new Set([
  "1m",
  "3m",
  "5m",
  "15m",
  "30m",
  "1h",
]);

export interface UseChartScrollbackOptions {
  symbol: string;
  exchange: Exchange;
  timeframe: Timeframe;
  /** Override the env-based mock toggle. Tests use this to skip
   *  network. */
  forceMock?: boolean;
  /** How many bars per fetch. Defaults to 200, matching the
   *  initial-history window. */
  barCount?: number;
}

export interface UseChartScrollbackState {
  /** Bars older than the consumer's current candle window. Empty
   *  on mount; grows as ``requestOlder`` resolves. */
  olderCandles: Candle[];
  /** ``true`` while a ``fetchOlderHistory`` call is in flight. */
  isLoadingOlder: boolean;
  /** ``true`` once the cumulative scroll-back has passed the
   *  5-year cap (intraday timeframes only — daily is uncapped
   *  here because the backend already enforces a 20-year ceiling). */
  hasReachedCap: boolean;
  /** Last fetch error or ``null``. Cleared on next successful
   *  fetch or on (symbol, timeframe) change. */
  error: Error | null;
  /** Fire to fetch the next ~200 bars older than ``beforeEpoch``.
   *  Idempotent — no-op if already loading or cap reached. */
  requestOlder: (beforeEpochSeconds: number) => void;
  /** Reset path for tests + parent-driven recovery. */
  reset: () => void;
}

export function useChartScrollback(
  opts: UseChartScrollbackOptions,
): UseChartScrollbackState {
  const { symbol, exchange, timeframe, forceMock, barCount = 200 } = opts;

  const [olderCandles, setOlderCandles] = useState<Candle[]>([]);
  const [isLoadingOlder, setIsLoadingOlder] = useState(false);
  const [hasReachedCap, setHasReachedCap] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Mount-version ref — bumped on every (symbol, exchange, timeframe)
  // change to discard in-flight fetches whose response would no
  // longer match the chart's current view.
  const versionRef = useRef(0);
  // Track the earliest epoch fetched so we can enforce the cap
  // without keeping the full ``olderCandles`` in scope of the cap
  // logic.
  const earliestFetchedRef = useRef<number | null>(null);
  const initialAnchorRef = useRef<number | null>(null);
  // Synchronous in-flight gate. ``setIsLoadingOlder`` is async so a
  // burst of synchronous ``requestOlder`` calls (chart fires the
  // logical-range handler many times during a fast left-scroll)
  // would otherwise all observe the stale ``isLoadingOlder=false``
  // and stack concurrent fetches. The ref flips synchronously
  // inside the call and cleans up in the finally block.
  const inFlightRef = useRef(false);
  // Same pattern for the cap so the synchronous burst is fully
  // gated.
  const capReachedRef = useRef(false);

  const reset = useCallback(() => {
    versionRef.current += 1;
    setOlderCandles([]);
    setIsLoadingOlder(false);
    setHasReachedCap(false);
    setError(null);
    earliestFetchedRef.current = null;
    initialAnchorRef.current = null;
    inFlightRef.current = false;
    capReachedRef.current = false;
  }, []);

  // Reset on (symbol, exchange, timeframe) change — a different
  // symbol's older bars would be nonsensical to keep prepended.
  useEffect(() => {
    reset();
  }, [symbol, exchange, timeframe, reset]);

  const requestOlder = useCallback(
    (beforeEpochSeconds: number) => {
      // Synchronous gate via refs — see ``inFlightRef`` definition
      // for why state is insufficient here.
      if (inFlightRef.current || capReachedRef.current) return;

      // Anchor the cap to the FIRST scroll-back trigger so the user
      // can scroll back ~5 years from where they started, regardless
      // of how much initial history was preloaded.
      if (initialAnchorRef.current === null) {
        initialAnchorRef.current = beforeEpochSeconds;
      }
      const anchor = initialAnchorRef.current;
      if (
        INTRADAY_TIMEFRAMES.has(timeframe) &&
        anchor - beforeEpochSeconds >= FIVE_YEARS_SECONDS
      ) {
        capReachedRef.current = true;
        setHasReachedCap(true);
        return;
      }

      const reqVersion = versionRef.current;
      inFlightRef.current = true;
      setIsLoadingOlder(true);
      setError(null);

      void (async () => {
        try {
          const resp = await fetchOlderHistory({
            symbol,
            exchange,
            timeframe,
            beforeEpochSeconds,
            barCount,
            forceMock,
          });
          if (reqVersion !== versionRef.current) return; // stale
          const parsed = resp.candles
            .map(parseCandle)
            .sort((a, b) => a.time - b.time);
          if (parsed.length === 0) {
            capReachedRef.current = true;
            setHasReachedCap(true);
            return;
          }
          earliestFetchedRef.current = parsed[0].time;
          setOlderCandles((prev) => [...parsed, ...prev]);
        } catch (err) {
          if (reqVersion !== versionRef.current) return;
          setError(
            err instanceof Error
              ? err
              : new Error("older-history fetch failed"),
          );
        } finally {
          if (reqVersion === versionRef.current) {
            inFlightRef.current = false;
            setIsLoadingOlder(false);
          }
        }
      })();
    },
    [symbol, exchange, timeframe, barCount, forceMock],
  );

  return {
    olderCandles,
    isLoadingOlder,
    hasReachedCap,
    error,
    requestOlder,
    reset,
  };
}
