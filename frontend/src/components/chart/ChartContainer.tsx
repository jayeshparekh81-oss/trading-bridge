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

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { CandlestickChart } from "./CandlestickChart";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import { SessionExpiredBanner } from "./SessionExpiredBanner";
import { StatusPill } from "./StatusPill";
import { SymbolSelector } from "./SymbolSelector";
import { TimeframeSelector } from "./TimeframeSelector";
import { useChartHistory } from "@/hooks/useChartHistory";
import { useChartWebSocket } from "@/hooks/useChartWebSocket";
import { useWsToken } from "@/hooks/useWsToken";
import type { Exchange, Timeframe } from "@/lib/chart/types";

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
  const candles = ws.candles.length > 0 ? ws.candles : history.candles;

  const showLoading = history.isLoading && candles.length === 0;
  const showFetchError =
    history.error !== null && candles.length === 0;

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
        <div className="flex items-center gap-3">
          <TimeframeSelector value={timeframe} onChange={setTimeframe} />
          <StatusPill
            status={ws.status}
            reconnectAttempt={ws.reconnectAttempt}
            onManualReconnect={ws.manualReconnect}
          />
        </div>
      </div>

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
          <CandlestickChart candles={candles} />
        )}
      </div>
    </div>
  );
}
