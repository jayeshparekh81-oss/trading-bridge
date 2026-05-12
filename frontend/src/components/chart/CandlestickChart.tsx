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
 * Phase 2 (crosshair OHLCV tooltip):
 *   - ``chart.subscribeCrosshairMove`` event drives a React-rendered
 *     absolutely-positioned overlay div ("ChartTooltip"). The handler
 *     looks up the hovered candle by ``time`` from the most-recent
 *     candle prop, and the overlay renders OHLCV with up/down accent.
 *   - Lightweight Charts v4 has no built-in tooltip primitive, so the
 *     React overlay path is the canonical approach (cited in the
 *     library's own examples).
 *
 * Performance contract (master brief quality bar):
 *   - Tail-only updates use ``series.update(...)`` (O(1)) so live
 *     tick → render stays under 50ms even on a 200-bar series.
 *   - Full ``setData`` only fires when the candle array's identity
 *     changes (memoised via referential equality of the prop) —
 *     prevents wasted full re-renders on heartbeat frames that
 *     don't change ``candles``.
 *   - Crosshair handler is the same closure across renders (uses a
 *     ref to read the latest candles) — avoids subscribe/unsubscribe
 *     churn on every tick.
 */

"use client";

import {
  CandlestickSeriesPartialOptions,
  ColorType,
  CrosshairMode,
  HistogramData,
  IChartApi,
  ISeriesApi,
  LogicalRange,
  MouseEventParams,
  SeriesMarker,
  Time,
  UTCTimestamp,
  createChart,
} from "lightweight-charts";
import { useEffect, useRef, useState } from "react";

import type { Candle, ChartMarker } from "@/lib/chart/types";

// ═══════════════════════════════════════════════════════════════════════
// Theme — dark only for Day 5
// ═══════════════════════════════════════════════════════════════════════

const DARK_THEME = {
  layout: {
    background: { type: ColorType.Solid, color: "#0a0a0a" },
    textColor: "#d4d4d4",
    // C10: suppress the default TradingView attribution overlay
    // on the chart canvas. Per Lightweight Charts' license, the
    // attribution requirement is fulfilled elsewhere (NOTICE file
    // + the TradingView link on the public pricing / about page) —
    // see node_modules/lightweight-charts NOTICE for the license
    // text. Disable here so the chart canvas stays unmarred.
    attributionLogo: false,
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

// Phase 3 — volume pane lives on a dedicated price-scale id with
// its own scale margins. The price-series scale margins are also
// re-applied so the two panes split the canvas cleanly: price gets
// the top ~73%, volume the bottom ~25%, with a 2% gap between.
const VOLUME_PRICE_SCALE_ID = "volume";
const VOLUME_UP_COLOR = "rgba(34, 197, 94, 0.55)"; // green-500 @ 55%
const VOLUME_DOWN_COLOR = "rgba(239, 68, 68, 0.55)"; // red-500 @ 55%
const PRICE_SCALE_MARGINS = { top: 0.05, bottom: 0.27 };
const VOLUME_SCALE_MARGINS = { top: 0.75, bottom: 0 };

function makeVolumeBar(c: Candle): HistogramData<UTCTimestamp> {
  return {
    time: c.time as UTCTimestamp,
    value: c.volume,
    color: c.close >= c.open ? VOLUME_UP_COLOR : VOLUME_DOWN_COLOR,
  };
}

/** Returns true iff at least one candle has a positive volume value.
 *  Backend feeds without volume (some option chains, certain MCX
 *  symbols) come through as zeros — rendering an all-zero histogram
 *  is just visual clutter. */
function candlesHaveVolume(candles: Candle[]): boolean {
  for (const c of candles) {
    if (typeof c.volume === "number" && c.volume > 0) return true;
  }
  return false;
}

// Tooltip layout constants — kept module-scoped so jsdom-free tests
// can assert positioning rules without re-deriving the magic numbers.
const TOOLTIP_OFFSET_PX = 14;
const TOOLTIP_WIDTH_PX = 168;
const TOOLTIP_HEIGHT_PX = 132;

// ═══════════════════════════════════════════════════════════════════════
// Tooltip state shape
// ═══════════════════════════════════════════════════════════════════════

interface TooltipState {
  /** Container-relative X anchor (chart coordinate, pixels). */
  x: number;
  /** Container-relative Y anchor (chart coordinate, pixels). */
  y: number;
  candle: Candle;
}

// ═══════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════

function findCandleByTime(
  candles: Candle[],
  time: number,
): Candle | undefined {
  // Binary search: candles are sorted ascending by time. Hot path on
  // every crosshair move so O(log N) matters even at N=200.
  let lo = 0;
  let hi = candles.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >>> 1;
    const t = candles[mid].time;
    if (t === time) return candles[mid];
    if (t < time) lo = mid + 1;
    else hi = mid - 1;
  }
  return undefined;
}

/** Clamp tooltip into the container so the overlay never spills past
 *  the chart's right or bottom edge. Cursor offset (TOOLTIP_OFFSET_PX)
 *  pulls the tooltip away from the crosshair so it doesn't sit on top
 *  of the candle being inspected. */
function clampTooltipPosition(
  x: number,
  y: number,
  containerWidth: number,
  containerHeight: number,
): { left: number; top: number } {
  const desiredLeft = x + TOOLTIP_OFFSET_PX;
  const desiredTop = y + TOOLTIP_OFFSET_PX;
  const maxLeft = Math.max(0, containerWidth - TOOLTIP_WIDTH_PX - 4);
  const maxTop = Math.max(0, containerHeight - TOOLTIP_HEIGHT_PX - 4);
  return {
    left: Math.min(Math.max(0, desiredLeft), maxLeft),
    top: Math.min(Math.max(0, desiredTop), maxTop),
  };
}

function formatPrice(value: number): string {
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatVolume(value: number): string {
  if (value >= 1e7) return `${(value / 1e7).toFixed(2)}Cr`;
  if (value >= 1e5) return `${(value / 1e5).toFixed(2)}L`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toLocaleString("en-IN");
}

function formatTooltipTime(epochSeconds: number): string {
  // IST locale — operator's traders read times in IST. Match the
  // chart's bottom-axis convention (HH:mm only, no seconds).
  const d = new Date(epochSeconds * 1000);
  return d.toLocaleString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "short",
    timeZone: "Asia/Kolkata",
  });
}

// ═══════════════════════════════════════════════════════════════════════
// Tooltip presentational sub-component (exported for unit testing)
// ═══════════════════════════════════════════════════════════════════════

export interface ChartTooltipProps {
  candle: Candle;
  left: number;
  top: number;
}

export function ChartTooltip({ candle, left, top }: ChartTooltipProps) {
  const isUp = candle.close >= candle.open;
  const accentClass = isUp ? "text-green-500" : "text-red-500";
  return (
    <div
      data-testid="chart-tooltip"
      data-direction={isUp ? "up" : "down"}
      className="pointer-events-none absolute z-10 rounded-md border border-neutral-700 bg-neutral-900/95 p-2 text-xs text-neutral-200 shadow-lg backdrop-blur-sm"
      style={{
        left,
        top,
        width: TOOLTIP_WIDTH_PX,
      }}
    >
      <div className="mb-1 text-[10px] uppercase tracking-wide text-neutral-400">
        {formatTooltipTime(candle.time)}
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 font-mono">
        <span className="text-neutral-400">O</span>
        <span className="text-right" data-testid="tt-open">
          {formatPrice(candle.open)}
        </span>
        <span className="text-neutral-400">H</span>
        <span className="text-right" data-testid="tt-high">
          {formatPrice(candle.high)}
        </span>
        <span className="text-neutral-400">L</span>
        <span className="text-right" data-testid="tt-low">
          {formatPrice(candle.low)}
        </span>
        <span className="text-neutral-400">C</span>
        <span
          className={`text-right ${accentClass}`}
          data-testid="tt-close"
        >
          {formatPrice(candle.close)}
        </span>
        <span className="text-neutral-400">V</span>
        <span
          className="text-right text-neutral-300"
          data-testid="tt-volume"
        >
          {formatVolume(candle.volume ?? 0)}
        </span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// Props
// ═══════════════════════════════════════════════════════════════════════

export interface CandlestickChartProps {
  candles: Candle[];
  /** Test seam — inject a fake ``createChart`` to skip canvas DOM
   *  setup in jsdom. Production callers should never pass this. */
  createChartFn?: typeof createChart;
  /** Phase 5 — fired when the user scrolls into the leftmost
   *  ``SCROLLBACK_TRIGGER_FRACTION`` of the loaded data. The handler
   *  receives the epoch (seconds) of the currently-leftmost candle
   *  so the parent's scrollback hook can build the next ``before``
   *  query. The chart is gating-agnostic — the parent owns
   *  ``isLoadingOlder`` + ``hasReachedCap`` and just stops calling
   *  back when those flip. */
  onRequestOlderHistory?: (earliestEpochSeconds: number) => void;
  /** Phase 5 — render the left-edge spinner overlay while a
   *  scroll-back fetch is in flight. The chart canvas continues
   *  to be interactive underneath. */
  isLoadingOlder?: boolean;
  /** Day 3 / Phase 1 — paper-trading markers to overlay. The
   *  chart calls ``series.setMarkers([...])`` whenever the array
   *  reference changes. Pass ``[]`` to clear. */
  markers?: ChartMarker[];
  /** Day 3 / Phase 1 — id of the currently-highlighted marker
   *  (driven by ``PaperTradeList`` row click). The chart re-runs
   *  setMarkers with the matching marker rendered at size=2 +
   *  centres the visible time-range on it. */
  highlightedMarkerId?: string | null;
  /** Day 3 / Phase 1 — fired when the user clicks on a marker on
   *  the canvas. The parent routes the id back into
   *  ``highlightedMarkerId`` (closing the loop) and into the
   *  PaperTradeList's scroll-into-view handler. */
  onMarkerClick?: (markerId: string) => void;
}

/** Fire onRequestOlderHistory once the visible logical range's
 *  ``from`` index drops into the leftmost 20% of the loaded data.
 *  Tunable trade-off: smaller value → fetch later (less aggressive
 *  prefetch, less wasted bandwidth on idle scroll-back); larger
 *  value → fetch earlier (smoother scroll, more chance the older
 *  bars are already prepended before the user reaches the edge). */
const SCROLLBACK_TRIGGER_FRACTION = 0.2;

// ═══════════════════════════════════════════════════════════════════════
// Day 3 / Phase 1 — markers overlay
// ═══════════════════════════════════════════════════════════════════════

const MARKER_COLORS: Record<ChartMarker["kind"], string> = {
  ENTRY: "#22c55e", // green-500
  EXIT: "#737373", // neutral-500
  SL_HIT: "#ef4444", // red-500
  TP_HIT: "#3b82f6", // blue-500
};

/** Stable per-marker id derived from kind + time. Mirrors
 *  PaperTradeList.markerId so the chart-side and list-side
 *  highlight handshake uses the same fingerprint without the two
 *  modules importing from each other. */
function chartMarkerId(m: ChartMarker): string {
  return `${m.kind}:${m.time}`;
}

/** Translate a ChartMarker into the Lightweight Charts v4
 *  ``SeriesMarker`` shape:
 *    * ENTRY  → arrowUp  belowBar (anchored at price candle's low,
 *                visually "buy from down here")
 *    * EXIT   → square   aboveBar (neutral, generic exit)
 *    * SL_HIT → arrowDown aboveBar (red, "stopped out from above")
 *    * TP_HIT → circle   aboveBar (blue, "target hit above")
 *
 * The ``id`` field on SeriesMarker is what subscribeClick-style
 * handlers receive in MouseEventParams.hoveredObjectId. */
function toLwcMarker(
  m: ChartMarker,
  highlighted: boolean,
): SeriesMarker<UTCTimestamp> {
  const kindShape: Record<ChartMarker["kind"], SeriesMarker<UTCTimestamp>["shape"]> = {
    ENTRY: "arrowUp",
    EXIT: "square",
    SL_HIT: "arrowDown",
    TP_HIT: "circle",
  };
  const kindPos: Record<ChartMarker["kind"], SeriesMarker<UTCTimestamp>["position"]> = {
    ENTRY: "belowBar",
    EXIT: "aboveBar",
    SL_HIT: "aboveBar",
    TP_HIT: "aboveBar",
  };
  return {
    time: m.time as UTCTimestamp,
    position: kindPos[m.kind],
    shape: kindShape[m.kind],
    color: MARKER_COLORS[m.kind],
    id: chartMarkerId(m),
    text: m.exit_reason ?? undefined,
    // Highlighted markers render a touch larger so the chart-list
    // handshake produces a visible flash on the canvas side too.
    size: highlighted ? 2 : 1,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════════

export function CandlestickChart({
  candles,
  createChartFn = createChart,
  onRequestOlderHistory,
  isLoadingOlder = false,
  markers,
  highlightedMarkerId = null,
  onMarkerClick,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  // Phase 3 — volume histogram series. Lazily created by the data-sync
  // effect on the FIRST render where the candle array carries any
  // positive volume value. Once created, lives for the chart's
  // lifetime (cleaned up implicitly via ``chart.remove()``).
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const lastCandleTimeRef = useRef<number | null>(null);
  // Phase 5 — track the current head epoch so the data-sync effect
  // can detect "older bars prepended" (head changed) vs "live tick
  // appended" (tail changed) and route to the correct LWC API path.
  const lastHeadTimeRef = useRef<number | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  // Mirror the latest candles into a ref so the crosshair handler
  // (created once at mount) reads the current array without forcing
  // a subscribe/unsubscribe cycle on every prop change.
  const candlesRef = useRef<Candle[]>(candles);
  candlesRef.current = candles;
  // Phase 5 — mirror the scrollback callback into a ref so the
  // logical-range handler stays stable across renders, mirroring
  // the crosshair handler's pattern.
  const onRequestOlderHistoryRef = useRef(onRequestOlderHistory);
  onRequestOlderHistoryRef.current = onRequestOlderHistory;
  // Day 3 / Phase 1 — same ref-mirror pattern for the marker click
  // callback. Click events fire through the chart's
  // subscribeClick handler that's installed once at mount.
  const onMarkerClickRef = useRef(onMarkerClick);
  onMarkerClickRef.current = onMarkerClick;

  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

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

    // Phase 3 — push the candle series upward so the bottom strip
    // is reserved for the volume histogram. The histogram series
    // itself is created lazily in the data-sync effect (first
    // candles array with positive volume), but the price-scale
    // margins must be applied at mount to avoid a visual jump
    // when the histogram appears.
    series.priceScale().applyOptions({ scaleMargins: PRICE_SCALE_MARGINS });

    // Phase 2: crosshair → React tooltip overlay. Reads from
    // candlesRef so the handler stays stable across data changes.
    const crosshairHandler = (param: MouseEventParams<Time>) => {
      // ``point`` is undefined when the crosshair leaves the chart
      // OR hovers in an area without data — in either case clear.
      if (!param.point || param.time === undefined) {
        setTooltip((prev) => (prev === null ? prev : null));
        return;
      }
      const t = Number(param.time);
      const found = findCandleByTime(candlesRef.current, t);
      if (!found) {
        setTooltip((prev) => (prev === null ? prev : null));
        return;
      }
      setTooltip({ x: param.point.x, y: param.point.y, candle: found });
    };
    chart.subscribeCrosshairMove(crosshairHandler);

    // Phase 5 — scrollback trigger. Fires when the visible logical
    // range's ``from`` index drops into the leftmost 20% of the
    // currently-loaded data. Reads ``candlesRef`` so the handler is
    // stable across renders.
    const logicalRangeHandler = (range: LogicalRange | null) => {
      if (!range) return;
      const handler = onRequestOlderHistoryRef.current;
      if (!handler) return;
      const arr = candlesRef.current;
      if (arr.length === 0) return;
      // Trigger when from < length × fraction. ``range.from`` may be
      // negative (panned past the leftmost bar) — the comparison
      // still holds.
      if (range.from < arr.length * SCROLLBACK_TRIGGER_FRACTION) {
        handler(arr[0].time);
      }
    };
    chart.timeScale().subscribeVisibleLogicalRangeChange(logicalRangeHandler);

    // Day 3 / Phase 1 — marker click handler. Lightweight Charts
    // routes the SeriesMarker.id of the clicked marker into
    // ``param.hoveredObjectId`` (when present); the chart's
    // ``subscribeClick`` is the canonical event for both candle
    // clicks and marker clicks. We only fire onMarkerClick when
    // a marker id is the click target — bare-canvas clicks are
    // ignored so they don't accidentally clear the highlight.
    const clickHandler = (param: MouseEventParams<Time>) => {
      const handler = onMarkerClickRef.current;
      if (!handler) return;
      const id = param.hoveredObjectId;
      if (typeof id === "string") {
        handler(id);
      }
    };
    chart.subscribeClick(clickHandler);

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
      chart.unsubscribeCrosshairMove(crosshairHandler);
      chart.unsubscribeClick(clickHandler);
      chart
        .timeScale()
        .unsubscribeVisibleLogicalRangeChange(logicalRangeHandler);
      observer.disconnect();
      resizeObserverRef.current = null;
      seriesRef.current = null;
      volumeSeriesRef.current = null;
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
    const chart = chartRef.current;
    if (!series || !chart) return;
    if (candles.length === 0) {
      series.setData([]);
      volumeSeriesRef.current?.setData([]);
      lastCandleTimeRef.current = null;
      lastHeadTimeRef.current = null;
      return;
    }

    const head = candles[0];
    const tail = candles[candles.length - 1];
    const prev = lastCandleTimeRef.current;
    const prevHead = lastHeadTimeRef.current;

    // Phase 3 — lazy-create the volume series the first time we see
    // a candles array with at least one positive volume entry. If
    // the feed never carries volume (some option chains, certain
    // MCX symbols), we never create the series and the chart
    // renders price-only — log once to surface the silent skip.
    if (
      volumeSeriesRef.current === null &&
      candlesHaveVolume(candles)
    ) {
      const volume = chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: VOLUME_PRICE_SCALE_ID,
      });
      volume
        .priceScale()
        .applyOptions({ scaleMargins: VOLUME_SCALE_MARGINS });
      volumeSeriesRef.current = volume;
    } else if (
      volumeSeriesRef.current === null &&
      !candlesHaveVolume(candles) &&
      prev === null
    ) {
      console.warn(
        "[chart] candles carry no positive volume — skipping volume pane",
      );
    }
    const vol = volumeSeriesRef.current;

    if (prev === null) {
      // First paint — full setData + fitContent so the entire
      // historical preload is visibly rendered. Without fitContent
      // the chart's default visible logical range is computed from
      // barSpacing × container width, and subsequent live ``update``
      // calls auto-pan the right edge — together those silently
      // push the historical 200-bar preload off-screen on narrow
      // viewports. fitContent runs once per series lifetime (gated
      // by prev === null); user pan/zoom afterwards is preserved.
      series.setData(
        candles.map((c) => ({
          time: c.time as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })),
      );
      vol?.setData(candles.map(makeVolumeBar));
      chartRef.current?.timeScale().fitContent();
    } else if (
      prevHead !== null &&
      head.time !== prevHead &&
      tail.time === prev
    ) {
      // Phase 5 — head changed AND tail unchanged → older bars were
      // prepended via the scroll-back loader. Full setData is the
      // only LWC API path that re-rasterises the prepended segment.
      // Crucially we do NOT call fitContent here: that would zoom
      // out and lose the user's scroll position, undoing the very
      // interaction that triggered the fetch.
      series.setData(
        candles.map((c) => ({
          time: c.time as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })),
      );
      vol?.setData(candles.map(makeVolumeBar));
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
      vol?.update(makeVolumeBar(tail));
    } else {
      // Symbol/timeframe change shipped a fully new array whose tail
      // time is < the previous tail. Fall back to full setData and
      // re-fit so the new series is visible (the prior fit's logical
      // range no longer maps to anything sensible).
      series.setData(
        candles.map((c) => ({
          time: c.time as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })),
      );
      vol?.setData(candles.map(makeVolumeBar));
      chartRef.current?.timeScale().fitContent();
    }
    lastCandleTimeRef.current = tail.time;
    lastHeadTimeRef.current = head.time;
  }, [candles]);

  // ── Day 3 / Phase 1 — markers sync ────────────────────────────────
  // Re-runs whenever the markers prop changes OR the highlight
  // changes. setMarkers is idempotent and replaces the full set, so
  // this is the simplest correct shape — performance is fine because
  // marker counts are tiny (< 100 per strategy window).
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    if (!markers || markers.length === 0) {
      series.setMarkers([]);
      return;
    }
    series.setMarkers(
      markers.map((m) =>
        toLwcMarker(m, chartMarkerId(m) === highlightedMarkerId),
      ),
    );
  }, [markers, highlightedMarkerId]);

  // ── Day 3 / Phase 1 — centre time-range on the highlighted marker
  // when the highlight changes from row click. The chart-side flash
  // is the size=2 marker; this scroll keeps the marker on-screen so
  // the operator doesn't have to pan to find it.
  useEffect(() => {
    if (highlightedMarkerId === null) return;
    if (!markers || markers.length === 0) return;
    const target = markers.find(
      (m) => chartMarkerId(m) === highlightedMarkerId,
    );
    if (!target) return;
    const ts = chartRef.current?.timeScale();
    if (!ts) return;
    const range = ts.getVisibleRange();
    if (!range) return;
    const from = Number(range.from);
    const to = Number(range.to);
    if (target.time >= from && target.time <= to) return;
    // Centre by setting a window with the same width as current.
    const halfWidth = (to - from) / 2;
    ts.setVisibleRange({
      from: (target.time - halfWidth) as UTCTimestamp,
      to: (target.time + halfWidth) as UTCTimestamp,
    });
  }, [highlightedMarkerId, markers]);

  const containerEl = containerRef.current;
  const tooltipPosition =
    tooltip && containerEl
      ? clampTooltipPosition(
          tooltip.x,
          tooltip.y,
          containerEl.clientWidth,
          containerEl.clientHeight,
        )
      : null;

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full"
      data-testid="candlestick-chart-container"
    >
      {tooltip && tooltipPosition && (
        <ChartTooltip
          candle={tooltip.candle}
          left={tooltipPosition.left}
          top={tooltipPosition.top}
        />
      )}
      {isLoadingOlder && (
        <div
          data-testid="chart-older-loading"
          className="pointer-events-none absolute left-2 top-1/2 z-10 flex -translate-y-1/2 items-center gap-2 rounded-md border border-neutral-700 bg-neutral-900/90 px-2 py-1 text-[11px] text-neutral-200 shadow"
        >
          <span
            data-testid="chart-older-loading-spinner"
            className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-neutral-500 border-t-neutral-100"
          />
          Loading…
        </div>
      )}
    </div>
  );
}
