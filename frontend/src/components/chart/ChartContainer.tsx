/**
 * ChartContainer — top-level orchestrator for the /chart route.
 *
 * Owns the (symbol, timeframe) state and wires together:
 *   - useWsToken  → 15-min JWT, 12-min refresh (R3)
 *   - useChartHistory → REST initial load
 *   - useChartWebSocket → live tick stream + reconnect (R2)
 *   - CandlestickChart → Lightweight Charts canvas (R1)
 *   - SymbolSelector / TimeframeSelector → user input
 *   - LoadingState / ErrorState → UI states
 *
 * Layout: top bar with selectors, then the chart fills the remaining
 * vertical space. Mobile-baseline (R4): selectors stack at narrow
 * widths, non-critical chrome hidden via Tailwind ``sm:`` / ``md:``.
 *
 * Disconnect surface: when the WS hook reports ``disconnected``,
 * a sonner ``toast.error`` fires with a stable id so re-trips
 * replace (not stack). On any transition away from ``disconnected``
 * the toast is dismissed. The chart itself keeps rendering
 * historical candles so traders can still read the last-known
 * price — the toast is a non-blocking notification, consistent
 * with the rest of the dashboard's error UX.
 */

"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { CandlestickChart } from "./CandlestickChart";
import { ChartHeaderInfo } from "./ChartHeaderInfo";
import { ErrorState } from "./ErrorState";
import {
  IndicatorsDropdown,
  loadPersistedToggles,
  type IndicatorToggles,
} from "./IndicatorsDropdown";
import { LoadingState } from "./LoadingState";
import { markerId as markerIdFn, PaperTradeList } from "./PaperTradeList";
import { SessionExpiredBanner } from "./SessionExpiredBanner";
import { StatusPill } from "./StatusPill";
import { StrategySelector } from "./StrategySelector";
import { SymbolSelector } from "./SymbolSelector";
import { TimeframeSelector } from "./TimeframeSelector";
import { useChartHistory } from "@/hooks/useChartHistory";
import { useChartMarkers } from "@/hooks/useChartMarkers";
import { useChartScrollback } from "@/hooks/useChartScrollback";
import { useChartWebSocket } from "@/hooks/useChartWebSocket";
import { useWsToken } from "@/hooks/useWsToken";
import type {
  ChartMarker,
  Exchange,
  Timeframe,
} from "@/lib/chart/types";

// Stable id ensures repeat trips replace the existing toast rather
// than stack a new one. Module-scoped because the id space is global
// to the sonner Toaster mounted in providers.tsx.
const DISCONNECTED_TOAST_ID = "chart-broker-disconnected";
const SESSION_EXPIRED_TOAST_ID = "chart-session-expired";

export interface ChartContainerProps {
  /** Initial symbol. Defaults to NIFTY for the launch demo. */
  initialSymbol?: string;
  /** Initial timeframe. Defaults to 5m. */
  initialTimeframe?: Timeframe;
  /** Exchange — fixed at NSE for Day 5. Phase 2 adds a picker. */
  exchange?: Exchange;
}

export function ChartContainer({
  initialSymbol = "NIFTY",
  initialTimeframe = "5m",
  exchange = "NSE",
}: ChartContainerProps) {
  const [symbol, setSymbol] = useState(initialSymbol);
  const [timeframe, setTimeframe] = useState<Timeframe>(initialTimeframe);

  const tokenState = useWsToken();
  const history = useChartHistory({ symbol, exchange, timeframe });
  const ws = useChartWebSocket({
    symbol,
    timeframe,
    token: tokenState.token,
    tokenVersion: tokenState.version,
    initialCandles: history.candles,
    sessionExpired: tokenState.sessionExpired,
  });

  // Combine history candles + live upserts. The WS hook seeds its
  // reducer from ``initialCandles`` on every (symbol, timeframe)
  // change, so ``ws.candles`` is always the authoritative source
  // once the WS is reachable.
  const liveCandles =
    ws.candles.length > 0 ? ws.candles : history.candles;

  // Phase 5 — scroll-back lazy loader. Owns the older-bars buffer
  // and the in-flight gating; the chart fires
  // ``onRequestOlderHistory`` whose handler we route here. The merged
  // ``candles`` view is what the chart and the header info row both
  // consume. Older bars sit OUTSIDE the WS hook's reducer state so
  // a prepend doesn't trigger the seed-reset path that would erase
  // live ticks.
  const scrollback = useChartScrollback({ symbol, exchange, timeframe });
  const candles = useMemo(
    () =>
      scrollback.olderCandles.length > 0
        ? [...scrollback.olderCandles, ...liveCandles]
        : liveCandles,
    [scrollback.olderCandles, liveCandles],
  );

  const showLoading = history.isLoading && candles.length === 0;
  const showFetchError =
    history.error !== null && candles.length === 0;

  // ── Day 3 / Phase 1 — paper-trading markers ─────────────────────
  // Strategy state lives here; the StrategySelector reads/writes it
  // and persists per-(symbol, timeframe) to localStorage on its own.
  const [strategyId, setStrategyId] = useState<string | null>(null);
  // Mobile drawer toggle for the PaperTradeList. Desktop ignores
  // this — the panel is always visible at md+.
  const [tradesDrawerOpen, setTradesDrawerOpen] = useState(false);
  // The currently-highlighted marker id — driven by either chart
  // click (marker → list scroll) or list row click (list → chart
  // centre + size flash). Single source of truth so both surfaces
  // stay in lockstep.
  const [highlightedMarkerId, setHighlightedMarkerId] = useState<
    string | null
  >(null);
  // Derive the markers fetch window from the current candle buffer.
  // When candles are still loading, fromIso/toIso are null → the
  // hook stays disabled and won't fire. As soon as candles arrive,
  // the window snaps to [first.time, last.time].
  const fromIso = useMemo(
    () =>
      candles.length === 0
        ? null
        : new Date(candles[0].time * 1000).toISOString(),
    [candles],
  );
  const toIso = useMemo(
    () =>
      candles.length === 0
        ? null
        : new Date(candles[candles.length - 1].time * 1000).toISOString(),
    [candles],
  );
  const markersState = useChartMarkers({
    strategyId,
    symbol,
    timeframe,
    fromIso,
    toIso,
  });
  // Reset highlight whenever the markers array reference changes —
  // a stale highlight from a prior strategy/window would point at
  // a marker no longer in the list.
  useEffect(() => {
    setHighlightedMarkerId(null);
  }, [markersState.markers]);

  const handleMarkerClickFromChart = useCallback((id: string) => {
    setHighlightedMarkerId(id);
    setTradesDrawerOpen(true);
  }, []);
  const handleRowClickFromList = useCallback((m: ChartMarker) => {
    setHighlightedMarkerId(markerIdFn(m));
  }, []);

  // Overnight #2 / Phase 2 + 3 — indicator toggles. Loaded from
  // localStorage on first render (server falls back to the shipped
  // defaults). Toggles persist via IndicatorsDropdown's onChange.
  const [indicators, setIndicators] = useState<IndicatorToggles>(
    () => loadPersistedToggles(),
  );

  // Mirror the WS connection status into a sonner toast. The chart
  // canvas stays mounted underneath; the toast is the only chrome
  // change on disconnect. Stable toast id de-dupes repeat trips.
  useEffect(() => {
    if (ws.status.kind === "disconnected") {
      toast.error("Broker connection toot gaya", {
        id: DISCONNECTED_TOAST_ID,
        description: `${ws.status.reason} (${ws.status.failed_attempts} attempts since ${new Date(
          ws.status.since,
        ).toLocaleTimeString()})`,
      });
    } else {
      toast.dismiss(DISCONNECTED_TOAST_ID);
    }
  }, [ws.status]);

  // Dismiss the disconnect toast on unmount so it doesn't surface on
  // whatever page the user navigates to next.
  useEffect(() => {
    return () => {
      toast.dismiss(DISCONNECTED_TOAST_ID);
    };
  }, []);

  // B9: fire the session-expired toast exactly once per transition.
  // ``tokenState.sessionExpired`` may be re-evaluated on every render
  // (parent rerenders, intermediate state churn), so a transition-edge
  // ref guards against duplicate toasts. Resets on flip back to false.
  const sessionExpiredRef = useRef(false);
  useEffect(() => {
    if (tokenState.sessionExpired && !sessionExpiredRef.current) {
      toast.error("Session expire ho gaya", {
        id: SESSION_EXPIRED_TOAST_ID,
        description:
          "Wapas login karo to live updates resume honge — chart history visible rahega.",
      });
      sessionExpiredRef.current = true;
    } else if (!tokenState.sessionExpired && sessionExpiredRef.current) {
      toast.dismiss(SESSION_EXPIRED_TOAST_ID);
      sessionExpiredRef.current = false;
    }
  }, [tokenState.sessionExpired]);

  // Dismiss session-expired toast on unmount, same reason as the
  // disconnect toast above.
  useEffect(() => {
    return () => {
      toast.dismiss(SESSION_EXPIRED_TOAST_ID);
    };
  }, []);

  return (
    <div
      className="flex h-[calc(100vh-4rem)] flex-col gap-2 p-3 md:p-4"
      data-testid="chart-container"
    >
      {/* ── Top bar: symbol + timeframe + status pill ────────── */}
      <div
        className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
        data-testid="chart-top-bar"
      >
        <SymbolSelector value={symbol} onChange={setSymbol} />
        <div className="flex flex-wrap items-center gap-3">
          <StrategySelector
            symbol={symbol}
            timeframe={timeframe}
            value={strategyId}
            onChange={setStrategyId}
          />
          <TimeframeSelector value={timeframe} onChange={setTimeframe} />
          <IndicatorsDropdown
            value={indicators}
            onChange={setIndicators}
          />
          <StatusPill
            status={ws.status}
            reconnectAttempt={ws.reconnectAttempt}
            onManualReconnect={ws.manualReconnect}
          />
        </div>
      </div>

      {/* ── Phase 4: live price + day OHLCV summary. Sits between
            the top bar and the canvas; mobile collapses to price +
            % change via Tailwind ``sm:`` breakpoints inside the
            component. ── */}
      <ChartHeaderInfo symbol={symbol} candles={candles} />

      {/* ── B9: session-expired banner — between header and chart. ── */}
      {tokenState.sessionExpired && <SessionExpiredBanner />}

      {/* ── Body: chart / loading / error ────────────────────── */}
      <div className="relative flex-1 overflow-hidden rounded-lg border border-border bg-[#0a0a0a]">
        {showLoading && <LoadingState />}

        {showFetchError && (
          <ErrorState
            kind="fetch"
            message={history.error?.message ?? "Network error"}
            onRetry={history.refetch}
          />
        )}

        {!showLoading && !showFetchError && (
          <CandlestickChart
            candles={candles}
            onRequestOlderHistory={scrollback.requestOlder}
            isLoadingOlder={scrollback.isLoadingOlder}
            markers={markersState.markers}
            highlightedMarkerId={highlightedMarkerId}
            onMarkerClick={handleMarkerClickFromChart}
            showSMA20={indicators.sma20}
            showEMA50={indicators.ema50}
            showRSI={indicators.rsi}
            showMACD={indicators.macd}
          />
        )}
      </div>

      {/* ── Day 3 / Phase 1 — paper trade list. Collapsible bottom
            drawer on mobile (hidden until user taps "Trades"),
            inline 280px panel on desktop. ── */}
      <div className="md:block">
        <button
          type="button"
          data-testid="paper-trade-list-toggle"
          className="flex w-full items-center justify-between rounded-md border border-border bg-neutral-900 px-3 py-1.5 text-xs text-neutral-200 md:hidden"
          onClick={() => setTradesDrawerOpen((o) => !o)}
        >
          <span>
            Paper Trades
            {markersState.markers.length > 0 && (
              <span className="ml-2 text-neutral-500">
                ({markersState.markers.length})
              </span>
            )}
          </span>
          <span className="text-neutral-500">
            {tradesDrawerOpen ? "▾" : "▴"}
          </span>
        </button>
        <PaperTradeList
          markers={markersState.markers}
          isLoading={markersState.isLoading}
          hasLoaded={markersState.hasLoaded}
          error={markersState.error}
          strategySelected={strategyId !== null}
          highlightedMarkerId={highlightedMarkerId}
          onRowClick={handleRowClickFromList}
          isOpen={tradesDrawerOpen}
          onClose={() => setTradesDrawerOpen(false)}
        />
      </div>
    </div>
  );
}
