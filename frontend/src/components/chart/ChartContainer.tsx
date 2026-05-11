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
 * Status banner: when the WS hook reports ``disconnected``, an
 * inline ErrorState overlay surfaces above the chart. The chart
 * itself keeps rendering historical candles so traders can still
 * read the last-known price.
 */

"use client";

import { useState } from "react";

import { CandlestickChart } from "./CandlestickChart";
import { ErrorState } from "./ErrorState";
import { LoadingState } from "./LoadingState";
import { SymbolSelector } from "./SymbolSelector";
import { TimeframeSelector } from "./TimeframeSelector";
import { useChartHistory } from "@/hooks/useChartHistory";
import { useChartWebSocket } from "@/hooks/useChartWebSocket";
import { useWsToken } from "@/hooks/useWsToken";
import type { Exchange, Timeframe } from "@/lib/chart/types";

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
  });

  // Combine history candles + live upserts. The WS hook seeds its
  // reducer from ``initialCandles`` on every (symbol, timeframe)
  // change, so ``ws.candles`` is always the authoritative source
  // once the WS is reachable.
  const candles = ws.candles.length > 0 ? ws.candles : history.candles;

  const showLoading = history.isLoading && candles.length === 0;
  const showFetchError =
    history.error !== null && candles.length === 0;
  const showDisconnectedBanner = ws.status.kind === "disconnected";

  return (
    <div
      className="flex h-[calc(100vh-4rem)] flex-col gap-2 p-3 md:p-4"
      data-testid="chart-container"
    >
      {/* ── Top bar: symbol + timeframe ──────────────────────── */}
      <div
        className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
        data-testid="chart-top-bar"
      >
        <SymbolSelector value={symbol} onChange={setSymbol} />
        <TimeframeSelector value={timeframe} onChange={setTimeframe} />
      </div>

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
          <>
            <CandlestickChart candles={candles} />

            {showDisconnectedBanner && ws.status.kind === "disconnected" && (
              <div
                className="absolute top-2 left-1/2 z-10 -translate-x-1/2"
                data-testid="chart-disconnected-overlay"
              >
                <ErrorState
                  kind="broker_disconnected"
                  message={`${ws.status.reason} (${ws.status.failed_attempts} attempts since ${new Date(ws.status.since).toLocaleTimeString()})`}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
