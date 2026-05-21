/**
 * BacktestChartPanel — Lightweight Charts surface for backtest results.
 *
 * Queue EE / Milestone 3 (feat/milestone-3-frontend-chart). New file —
 * conforms to the parallel-CC "new-files-only" rule. Page integration
 * is described in `frontend/PATCH_INSTRUCTIONS_MILESTONE_3.md`.
 *
 * Wire contract:
 *   GET /api/backtest/{runId}/markers
 *     → { run_id: UUID, markers: ChartMarkerOut[] }
 *
 *   ChartMarkerOut is **already** Lightweight Charts' SeriesMarker
 *   shape (Queue CC+DD wire format) — no client-side adapter.
 *
 * Candle source: `fetchChartHistory` from `@/lib/chart/api` so auth,
 * mock toggle, and 401-refresh behave identically to the live `/chart`
 * route. The window is derived from the markers' [min, max] time ±
 * one bar of timeframe padding.
 *
 * States handled (per Queue EE brief, §Phase 2):
 *   - loading (skeleton)
 *   - 404 from markers → "Markers not available for this run"
 *   - 500 / network error → error + retry
 *   - markers OK but candles failed → markers-only fallback (time axis,
 *     no candles)
 *   - empty markers → "No trades in this backtest run"
 *
 * Reuse policy: this component does NOT delegate to <CandlestickChart>
 * — see frontend/docs/MILESTONE_3_FRONTEND_AUDIT.md §3 for the
 * rationale (marker-shape mismatch + WS/scrollback/indicator baggage).
 * It calls `createChart` directly with the same dark theme constants.
 */

"use client";

import {
  ColorType,
  CrosshairMode,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type UTCTimestamp,
  createChart,
} from "lightweight-charts";
import { AlertTriangle, BarChart3, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { api, ApiError } from "@/lib/api";
import { fetchChartHistory } from "@/lib/chart/api";
import {
  parseCandle,
  type Candle,
  type Exchange,
  type Timeframe,
} from "@/lib/chart/types";

// ─── Backend wire shape ─────────────────────────────────────────────────

/** Mirrors `app.backtest_extension.api.ChartMarkerOut`. */
interface ChartMarkerOut {
  time: number;
  position: "aboveBar" | "belowBar";
  color: string;
  shape: "arrowUp" | "arrowDown" | "circle";
  text: string;
}

interface ChartMarkersResponse {
  run_id: string;
  markers: ChartMarkerOut[];
}

// ─── Dark theme — mirrors CandlestickChart.tsx ─────────────────────────

const DARK_THEME = {
  layout: {
    background: { type: ColorType.Solid, color: "#0a0a0a" },
    textColor: "#d4d4d4",
    attributionLogo: false,
  },
  grid: {
    vertLines: { color: "#1f1f1f" },
    horzLines: { color: "#1f1f1f" },
  },
  crosshair: { mode: CrosshairMode.Normal },
  rightPriceScale: { borderColor: "#262626" },
  timeScale: {
    borderColor: "#262626",
    timeVisible: true,
    secondsVisible: false,
  },
} as const;

const CANDLE_COLORS = {
  upColor: "#22c55e",
  downColor: "#ef4444",
  borderUpColor: "#22c55e",
  borderDownColor: "#ef4444",
  wickUpColor: "#22c55e",
  wickDownColor: "#ef4444",
} as const;

// Timeframe-seconds for window padding around marker [min, max].
const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  "1m": 60,
  "3m": 180,
  "5m": 300,
  "15m": 900,
  "30m": 1_800,
  "1h": 3_600,
  "1d": 86_400,
};

// ─── Fetch state ────────────────────────────────────────────────────────

type FetchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "missing" } // 404
  | {
      kind: "error";
      message: string;
    }
  | {
      kind: "loaded";
      markers: ChartMarkerOut[];
      candles: Candle[];
      candlesFailed: boolean;
    };

// ─── Props ──────────────────────────────────────────────────────────────

export interface BacktestChartPanelProps {
  runId: string;
  strategyId: string;
  symbol: string;
  timeframe: Timeframe;
  /** Optional exchange override; defaults to NSE. */
  exchange?: Exchange;
  /** Test seam — inject a fake `createChart` to bypass canvas in jsdom. */
  createChartFn?: typeof createChart;
}

// ─── Component ──────────────────────────────────────────────────────────

export function BacktestChartPanel({
  runId,
  strategyId,
  symbol,
  timeframe,
  exchange = "NSE",
  createChartFn = createChart,
}: BacktestChartPanelProps) {
  const [state, setState] = useState<FetchState>({ kind: "idle" });
  const isAlive = useRef(true);

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      // Markers first — drives the candle window AND tells us early if
      // the run is missing/unavailable.
      const markersResp = await api.get<ChartMarkersResponse>(
        `/backtest/${runId}/markers`,
      );
      if (!isAlive.current) return;
      const markers = markersResp.markers;

      if (markers.length === 0) {
        setState({
          kind: "loaded",
          markers: [],
          candles: [],
          candlesFailed: false,
        });
        return;
      }

      // Derive window: [min - 1 bar, max + 1 bar] for visual padding.
      const tfSeconds = TIMEFRAME_SECONDS[timeframe];
      const minTime = markers.reduce(
        (acc, m) => (m.time < acc ? m.time : acc),
        markers[0].time,
      );
      const maxTime = markers.reduce(
        (acc, m) => (m.time > acc ? m.time : acc),
        markers[0].time,
      );
      const fromIso = new Date((minTime - tfSeconds) * 1000).toISOString();
      const toIso = new Date((maxTime + tfSeconds) * 1000).toISOString();

      let candles: Candle[] = [];
      let candlesFailed = false;
      try {
        const histResp = await fetchChartHistory({
          symbol,
          exchange,
          timeframe,
          from: fromIso,
          to: toIso,
        });
        if (!isAlive.current) return;
        candles = histResp.candles
          .map(parseCandle)
          .sort((a, b) => a.time - b.time);
      } catch {
        // Per Queue EE brief: candle failure → markers-only fallback.
        candlesFailed = true;
      }

      if (!isAlive.current) return;
      setState({
        kind: "loaded",
        markers,
        candles,
        candlesFailed,
      });
    } catch (err) {
      if (!isAlive.current) return;
      if (err instanceof ApiError && err.status === 404) {
        setState({ kind: "missing" });
        return;
      }
      const message =
        err instanceof Error ? err.message : "Backtest markers fetch failed";
      setState({ kind: "error", message });
    }
  }, [runId, symbol, exchange, timeframe]);

  useEffect(() => {
    isAlive.current = true;
    // setState-in-effect is intentional: fetch-on-mount kicks off the
    // markers/candles load and the first setState(loading) inside load()
    // is the React-correct way to surface the in-flight UI. The rule's
    // suggested alternatives (useSyncExternalStore, suspense) don't fit
    // a one-shot REST fetch keyed on props.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    return () => {
      isAlive.current = false;
    };
  }, [load]);

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-3" data-testid="backtest-chart-panel">
        <Header strategyId={strategyId} symbol={symbol} timeframe={timeframe} />
        <Body
          state={state}
          onRetry={load}
          createChartFn={createChartFn}
          // Stable key so the chart remounts cleanly on run/symbol change
          // rather than trying to swap series data mid-flight.
          chartKey={`${runId}:${symbol}:${timeframe}`}
        />
      </div>
    </GlassmorphismCard>
  );
}

// ─── Header ─────────────────────────────────────────────────────────────

function Header({
  strategyId,
  symbol,
  timeframe,
}: {
  strategyId: string;
  symbol: string;
  timeframe: Timeframe;
}) {
  return (
    <div className="flex items-center gap-2">
      <BarChart3 className="h-4 w-4 text-accent-blue" />
      <h3 className="font-semibold text-sm">Trade chart</h3>
      <span
        className="ml-auto text-[10px] text-muted-foreground font-mono"
        data-testid="backtest-chart-panel-meta"
      >
        {symbol} · {timeframe} · {strategyId.slice(0, 8)}
      </span>
    </div>
  );
}

// ─── Body — state machine ───────────────────────────────────────────────

function Body({
  state,
  onRetry,
  createChartFn,
  chartKey,
}: {
  state: FetchState;
  onRetry: () => void;
  createChartFn: typeof createChart;
  chartKey: string;
}) {
  if (state.kind === "idle" || state.kind === "loading") {
    return <LoadingSkeleton />;
  }
  if (state.kind === "missing") {
    return (
      <EmptyState
        message="Markers not available for this run"
        hint="The backtest may not have produced any persisted trades yet."
      />
    );
  }
  if (state.kind === "error") {
    return <ErrorState message={state.message} onRetry={onRetry} />;
  }
  // loaded
  if (state.markers.length === 0) {
    return (
      <EmptyState
        message="No trades in this backtest run"
        hint="The strategy did not generate any entry signals during this period."
      />
    );
  }
  return (
    <LightweightChart
      key={chartKey}
      candles={state.candles}
      markers={state.markers}
      candlesFailed={state.candlesFailed}
      createChartFn={createChartFn}
    />
  );
}

// ─── States ─────────────────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div
      data-testid="backtest-chart-panel-loading"
      className="animate-pulse h-64 rounded bg-white/[0.03]"
    />
  );
}

function EmptyState({
  message,
  hint,
}: {
  message: string;
  hint: string;
}) {
  return (
    <div
      data-testid="backtest-chart-panel-empty"
      className="flex h-64 flex-col items-center justify-center gap-1 rounded border border-dashed border-white/[0.08] text-center"
    >
      <p className="text-sm text-muted-foreground">{message}</p>
      <p className="text-xs text-muted-foreground/70">{hint}</p>
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      data-testid="backtest-chart-panel-error"
      className="flex h-64 flex-col items-center justify-center gap-2 rounded border border-loss/30 bg-loss/[0.04] text-center px-4"
    >
      <AlertTriangle className="h-6 w-6 text-loss" />
      <p className="text-sm font-medium">Chart load failed</p>
      <p className="text-xs text-muted-foreground max-w-md">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        data-testid="backtest-chart-panel-retry"
        className="mt-1 inline-flex items-center gap-1.5 rounded-md border border-white/[0.1] bg-white/[0.04] px-3 py-1 text-xs hover:bg-white/[0.08] transition-colors"
      >
        <RefreshCw className="h-3 w-3" />
        Retry
      </button>
    </div>
  );
}

// ─── Lightweight Charts surface ─────────────────────────────────────────

function LightweightChart({
  candles,
  markers,
  candlesFailed,
  createChartFn,
}: {
  candles: Candle[];
  markers: ChartMarkerOut[];
  candlesFailed: boolean;
  createChartFn: typeof createChart;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  // Mount: create chart + candlestick series + ResizeObserver.
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

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry || !chartRef.current) return;
      const { width, height } = entry.contentRect;
      chartRef.current.applyOptions({ width, height });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      seriesRef.current = null;
      chartRef.current = null;
      try {
        chart.remove();
      } catch {
        /* remove-time errors must not leak */
      }
    };
    // createChartFn is mount-only; runtime swap is not a supported scenario.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Data sync: candles + markers. Backend marker shape is already
  // SeriesMarker — no adapter needed beyond the UTCTimestamp cast.
  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;

    series.setData(
      candles.map((c) => ({
        time: c.time as UTCTimestamp,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
    const lwcMarkers: SeriesMarker<UTCTimestamp>[] = markers.map((m) => ({
      time: m.time as UTCTimestamp,
      position: m.position,
      color: m.color,
      shape: m.shape,
      text: m.text,
    }));
    series.setMarkers(lwcMarkers);
    chart.timeScale().fitContent();
  }, [candles, markers]);

  return (
    <div className="relative h-64 w-full md:h-80">
      {candlesFailed && (
        <div
          data-testid="backtest-chart-panel-candles-fallback"
          className="absolute left-2 top-2 z-10 rounded border border-white/[0.1] bg-neutral-900/90 px-2 py-1 text-[10px] text-muted-foreground"
        >
          Candles unavailable — markers shown on time axis only.
        </div>
      )}
      <div
        ref={containerRef}
        data-testid="backtest-chart-panel-canvas"
        className="h-full w-full overflow-hidden rounded border border-white/[0.06] bg-[#0a0a0a]"
      />
    </div>
  );
}

