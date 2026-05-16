/**
 * useTradeMarkers — Phase E hook for the Phase A ``/api/markers``
 * read path. Fetches the persistent trade-marker rows for one
 * ``(strategyId, mode)`` pair, parses the Decimal-string wire shape
 * into render-ready ``Marker`` rows, and pre-converts to the
 * Lightweight-Charts ``SeriesMarker`` shape so the canvas can drop the
 * array into ``series.setMarkers([...])`` unchanged.
 *
 * Pattern mirrors :mod:`@/hooks/useStrategyTester` +
 * :mod:`@/hooks/useChartMarkers`:
 *   - mount-version ref drops stale responses when deps change mid-flight
 *   - ``hasLoaded`` flag distinguishes "still loading initial data"
 *     from "loaded, empty result set"
 *   - ``enabled`` lets the consumer skip the fetch (e.g. before the
 *     user picks a strategy or before candles seed the time window)
 *
 * Error handling
 *   - 401: shared :mod:`@/lib/api` client auto-refreshes once, then
 *     throws ``ApiError(401)`` on refresh failure. Hook surfaces
 *     ``error`` + empty markers — consumer can redirect to login.
 *   - 403: backend collapses ownership + existence. Hook surfaces
 *     ``error`` with the backend's Hinglish detail and empty markers.
 *     A "no markers" empty-state on the chart is the right UX here —
 *     the strategy either doesn't exist or isn't yours.
 *   - 5xx / network: ``error`` populated, ``markers`` empty.
 *     ``refetch`` re-runs the fetch.
 *
 * Why a separate hook from ``useChartMarkers``
 *   The legacy hook (``/api/chart/markers``, paper-trade-derived) and
 *   the new hook (``/api/markers``, trade_markers-derived) coexist for
 *   one branch — the cutover (replacing the call site in
 *   ChartContainer) is documented in PATCH_INSTRUCTIONS_PHASE_E.md so
 *   it can roll back to the legacy source by reverting a single import.
 */

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchMarkers } from "@/lib/markers-overlay/api";
import { markersToSeriesMarkers } from "@/lib/markers-overlay/mapper";
import {
  parseTradeMarkerListResponse,
  type ChartSeriesMarker,
  type Marker,
  type MarkerMode,
  type MarkerSide,
} from "@/lib/markers-overlay/types";

export interface UseTradeMarkersOptions {
  strategyId: string | null;
  mode: MarkerMode;
  symbol?: string | null;
  /** ISO 8601 with tz offset. ``null`` = no lower bound. */
  fromIso?: string | null;
  /** ISO 8601 with tz offset. ``null`` = no upper bound. */
  toIso?: string | null;
  side?: MarkerSide | null;
  /** Backend default 100, max 500. */
  limit?: number;
  offset?: number;
  /** Currently-highlighted marker id — forwarded to the SeriesMarker
   *  mapper so the highlighted row renders at size=2 on the canvas.
   *  ``null`` = no highlight. */
  highlightedId?: string | null;
  /** Skip the fetch entirely. Defaults to ``strategyId !== null``. */
  enabled?: boolean;
}

export interface UseTradeMarkersResult {
  /** Ready-to-feed ``series.setMarkers(...)`` array (epoch seconds
   *  UTC, palette + shape resolved). */
  markers: ChartSeriesMarker[];
  /** Render-ready Marker rows (numeric price/pnl) — for non-canvas
   *  consumers (lists, drill-ins, exports). */
  rawMarkers: Marker[];
  isLoading: boolean;
  /** ``true`` once at least one fetch cycle has resolved. */
  hasLoaded: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

export function useTradeMarkers(
  opts: UseTradeMarkersOptions,
): UseTradeMarkersResult {
  const {
    strategyId,
    mode,
    symbol,
    fromIso,
    toIso,
    side,
    limit,
    offset,
    highlightedId,
    enabled,
  } = opts;

  const isReady = strategyId !== null;
  const effectiveEnabled = enabled ?? isReady;

  const [rawMarkers, setRawMarkers] = useState<Marker[]>([]);
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
    try {
      const wire = await fetchMarkers({
        strategyId,
        mode,
        symbol: symbol ?? null,
        fromIso: fromIso ?? null,
        toIso: toIso ?? null,
        side: side ?? null,
        limit: limit ?? null,
        offset: offset ?? null,
      });
      if (reqVersion !== versionRef.current) return;
      const parsed = parseTradeMarkerListResponse(wire);
      setRawMarkers(parsed.markers);
    } catch (err) {
      if (reqVersion !== versionRef.current) return;
      setRawMarkers([]);
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
    mode,
    symbol,
    fromIso,
    toIso,
    side,
    limit,
    offset,
  ]);

  useEffect(() => {
    if (!effectiveEnabled || !isReady) return;
    void load();
  }, [effectiveEnabled, isReady, load]);

  // Recompute the SeriesMarker shape only when the source rows or the
  // highlight target change — the mapper is O(n log n) (sort + map),
  // cheap for n < 500 but worth memoising so a parent-rerender doesn't
  // re-render the canvas with a fresh-but-equivalent array reference.
  const markers = useMemo(
    () => markersToSeriesMarkers(rawMarkers, { highlightedId }),
    [rawMarkers, highlightedId],
  );

  return {
    markers,
    rawMarkers,
    isLoading,
    hasLoaded,
    error,
    refetch: load,
  };
}
