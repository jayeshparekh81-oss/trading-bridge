/**
 * useStrategyTester — Phase D hook. Fetches the Phase B aggregation
 * triple (metrics + equity + trades) for one ``(strategyId, mode)``
 * pair in parallel and returns parsed, render-ready state.
 *
 * Pattern mirrors :mod:`@/hooks/useChartMarkers`:
 *   - mount-version ref drops stale responses when deps change mid-flight
 *   - ``hasLoaded`` flag distinguishes "still loading initial data"
 *     from "loaded, empty result set"
 *   - ``enabled`` lets the consumer skip the fetch (e.g. before the
 *     user picks a strategy)
 *
 * Error handling
 *   - 401: the shared :mod:`@/lib/api` client auto-refreshes once,
 *     then throws an ``ApiError(401)`` on refresh failure. Hook
 *     surfaces as ``error`` with empty state — consumer redirects to
 *     login.
 *   - 403: ownership/existence collapse on the backend. Hook
 *     surfaces as empty state with the backend's Hinglish detail —
 *     "no access OR no data".
 *   - 5xx / network: ``error`` populated, state cleared. ``refetch``
 *     re-runs all 3 in parallel.
 *
 * ``Promise.allSettled`` semantics — partial-success WITHOUT this
 * would block the whole panel on a single endpoint hiccup. With
 * ``allSettled`` the consumer can render whatever loaded; we surface
 * the first encountered error so the panel can show a banner.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  fetchStrategyTesterEquity,
  fetchStrategyTesterMetrics,
  fetchStrategyTesterTrades,
} from "@/lib/strategy-tester/api";
import {
  parseEquityCurveResponse,
  parseStrategyTesterMetrics,
  parseTradeListResponse,
  type EquityCurveResponse,
  type Mode,
  type StrategyTesterMetrics,
  type TradeListResponse,
} from "@/lib/strategy-tester/types";

export interface UseStrategyTesterOptions {
  strategyId: string | null;
  mode: Mode;
  /** ISO 8601 with tz offset. ``null`` = no lower bound. */
  fromIso?: string | null;
  /** ISO 8601 with tz offset. ``null`` = no upper bound. */
  toIso?: string | null;
  /** Trade-list page size (1..500). Backend default 100. */
  limit?: number;
  /** Trade-list offset. Backend default 0. */
  offset?: number;
  /** Symbol filter for the trade list (max 64 chars). */
  symbolFilter?: string | null;
  /** Starting equity for max-drawdown walk + equity-curve anchor. */
  startingEquity?: number;
  /** Skip the fetch entirely. Defaults to ``strategyId !== null``. */
  enabled?: boolean;
}

export interface UseStrategyTesterResult {
  metrics: StrategyTesterMetrics | null;
  equity: EquityCurveResponse | null;
  trades: TradeListResponse | null;
  isLoading: boolean;
  /** ``true`` once at least one fetch cycle has resolved. */
  hasLoaded: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useStrategyTester(
  opts: UseStrategyTesterOptions,
): UseStrategyTesterResult {
  const {
    strategyId,
    mode,
    fromIso,
    toIso,
    limit,
    offset,
    symbolFilter,
    startingEquity,
    enabled,
  } = opts;

  const isReady = strategyId !== null;
  const effectiveEnabled = enabled ?? isReady;

  const [metrics, setMetrics] = useState<StrategyTesterMetrics | null>(null);
  const [equity, setEquity] = useState<EquityCurveResponse | null>(null);
  const [trades, setTrades] = useState<TradeListResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Mount-version ref — bumped on every dep change so the resolve
  // path of an in-flight fetch can drop a stale response.
  const versionRef = useRef(0);

  const load = useCallback(async () => {
    if (!effectiveEnabled || !isReady || strategyId === null) {
      setIsLoading(false);
      return;
    }
    const reqVersion = ++versionRef.current;
    setIsLoading(true);
    setError(null);
    const baseOpts = {
      strategyId,
      mode,
      fromIso: fromIso ?? null,
      toIso: toIso ?? null,
      startingEquity: startingEquity ?? null,
    };
    const [metricsRes, equityRes, tradesRes] = await Promise.allSettled([
      fetchStrategyTesterMetrics(baseOpts),
      fetchStrategyTesterEquity(baseOpts),
      fetchStrategyTesterTrades({
        ...baseOpts,
        symbol: symbolFilter ?? null,
        limit: limit ?? null,
        offset: offset ?? null,
      }),
    ]);
    if (reqVersion !== versionRef.current) return;

    let firstError: Error | null = null;
    if (metricsRes.status === "fulfilled") {
      setMetrics(parseStrategyTesterMetrics(metricsRes.value));
    } else {
      setMetrics(null);
      firstError ??= toError(metricsRes.reason, "metrics fetch failed");
    }
    if (equityRes.status === "fulfilled") {
      setEquity(parseEquityCurveResponse(equityRes.value));
    } else {
      setEquity(null);
      firstError ??= toError(equityRes.reason, "equity fetch failed");
    }
    if (tradesRes.status === "fulfilled") {
      setTrades(parseTradeListResponse(tradesRes.value));
    } else {
      setTrades(null);
      firstError ??= toError(tradesRes.reason, "trades fetch failed");
    }
    setError(firstError);
    setIsLoading(false);
    setHasLoaded(true);
  }, [
    effectiveEnabled,
    isReady,
    strategyId,
    mode,
    fromIso,
    toIso,
    limit,
    offset,
    symbolFilter,
    startingEquity,
  ]);

  useEffect(() => {
    if (!effectiveEnabled || !isReady) return;
    void load();
  }, [effectiveEnabled, isReady, load]);

  return {
    metrics,
    equity,
    trades,
    isLoading,
    hasLoaded,
    error,
    refetch: load,
  };
}

function toError(reason: unknown, fallbackMsg: string): Error {
  if (reason instanceof Error) return reason;
  return new Error(fallbackMsg);
}
