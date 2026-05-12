/**
 * useChartMarkers — Phase 7 hook scaffold for the Day-3 markers
 * overlay. Fetches paper-trading markers for the requested
 * (strategy, symbol, timeframe, window) and returns them in the
 * render-ready ``ChartMarker[]`` form.
 *
 * Module status (Day 3 prep / scaffold)
 *   The hook is implemented + tested but NOT yet integrated into
 *   ChartContainer — see PATCH_INSTRUCTIONS_FRONTEND_DAY3.md for
 *   the manual integration step. The intent is to lock the wire
 *   contract today (matched to the backend Phase-6 schema) without
 *   shipping an unfinished feature on the live UI surface.
 *
 * Refresh semantics
 *   Refetch is triggered by changes to ``(strategyId, symbol,
 *   timeframe, fromIso, toIso, enabled)``. The ``enabled`` flag
 *   lets the consumer skip the fetch entirely (useful before the
 *   user picks a strategy).
 *
 * Window contract
 *   ``fromIso`` / ``toIso`` are ISO 8601 strings with tz offsets.
 *   The hook does not normalise them — passing the raw timestamps
 *   from the chart's first/last candle (rendered via
 *   ``new Date(time * 1000).toISOString()``) is the expected path.
 *   ``null`` for either value disables the fetch (waiting on
 *   candles to load).
 *
 * Authorisation note
 *   The backend route returns 403 for cross-user strategy access
 *   AND for missing strategies. The hook surfaces both as
 *   ``error`` (an Error with the backend's Hinglish detail). The
 *   consumer is responsible for translating that into UI.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchChartMarkers } from "@/lib/chart/api";
import {
  parseChartMarker,
  type ChartMarker,
  type Timeframe,
} from "@/lib/chart/types";

export interface UseChartMarkersOptions {
  strategyId: string | null;
  symbol: string;
  timeframe: Timeframe;
  /** ISO 8601 with tz offset. ``null`` disables the fetch. */
  fromIso: string | null;
  /** ISO 8601 with tz offset. ``null`` disables the fetch. */
  toIso: string | null;
  /** Skip the fetch entirely. Defaults to ``true`` when all required
   *  inputs are non-null. */
  enabled?: boolean;
  /** Test-injection override of the env-based mock toggle. */
  forceMock?: boolean;
}

export interface UseChartMarkersState {
  markers: ChartMarker[];
  isLoading: boolean;
  /** ``true`` once at least one fetch has resolved (success OR
   *  failure). Lets consumers distinguish "still loading initial
   *  data" from "loaded, found zero markers". */
  hasLoaded: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useChartMarkers(
  opts: UseChartMarkersOptions,
): UseChartMarkersState {
  const {
    strategyId,
    symbol,
    timeframe,
    fromIso,
    toIso,
    enabled,
    forceMock,
  } = opts;

  const isReady =
    strategyId !== null && fromIso !== null && toIso !== null;
  const effectiveEnabled = enabled ?? isReady;

  const [markers, setMarkers] = useState<ChartMarker[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Mount-version ref — bumped on every dep change so the resolve
  // path of an in-flight fetch can drop a stale response.
  const versionRef = useRef(0);

  const load = useCallback(async () => {
    if (!effectiveEnabled || !isReady) {
      setIsLoading(false);
      return;
    }
    const reqVersion = ++versionRef.current;
    setIsLoading(true);
    setError(null);
    try {
      const resp = await fetchChartMarkers({
        strategyId: strategyId!,
        symbol,
        timeframe,
        fromIso: fromIso!,
        toIso: toIso!,
        forceMock,
      });
      if (reqVersion !== versionRef.current) return;
      setMarkers(resp.markers.map(parseChartMarker));
    } catch (err) {
      if (reqVersion !== versionRef.current) return;
      setError(
        err instanceof Error ? err : new Error("markers fetch failed"),
      );
    } finally {
      if (reqVersion === versionRef.current) {
        setIsLoading(false);
        setHasLoaded(true);
      }
    }
  }, [
    effectiveEnabled,
    isReady,
    strategyId,
    symbol,
    timeframe,
    fromIso,
    toIso,
    forceMock,
  ]);

  useEffect(() => {
    if (!effectiveEnabled || !isReady) return;
    void load();
    // ``load`` is memoised on every meaningful dep; React's
    // exhaustive-deps lint is satisfied by including ``load`` here.
  }, [effectiveEnabled, isReady, load]);

  return { markers, isLoading, hasLoaded, error, refetch: load };
}
