/**
 * ChartHeaderInfo — Phase 4 live price + day OHLCV summary.
 *
 * Sits between the (symbol + timeframe + status) top bar and the
 * chart canvas in ChartContainer. Updates on every render the
 * parent triggers (typically a new candle arriving via the WS
 * upsert path), so the price stays live without any internal
 * state — ``candles`` is the single source of truth.
 *
 * Layout
 *   - Always visible: current price (large), absolute + percent
 *     change vs today's open. Mobile-essential pair, never hidden.
 *   - md+ viewports add: today's open / high / low / volume.
 *     Hidden under ``sm:`` because they crowd the narrow phone
 *     viewport and the chart canvas is the priority there.
 *
 * Day-window derivation (R4 mobile baseline)
 *   - "Today" = bars whose IST date matches the current IST date.
 *     This works cleanly for intraday timeframes (1m..1h) and
 *     for the daily timeframe falls through to the latest bar.
 *   - If today's window is empty (pre-market load with only
 *     yesterday's bars in the buffer), we fall back to the full
 *     candles array so the user sees something meaningful instead
 *     of a row of dashes.
 *   - Open = first today-bar's open. High = max(today.high).
 *     Low = min(today.low). Volume = Σ today.volume.
 *   - Change = lastCandle.close - todayOpen (intraday convention
 *     used by NSE, Zerodha, Dhan, Fyers — matches the operator's
 *     mental model better than overnight-close which we don't
 *     reliably have on intraday timeframes).
 */

"use client";

import { useMemo } from "react";

import type { Candle } from "@/lib/chart/types";

// ═══════════════════════════════════════════════════════════════════════
// Helpers
// ═══════════════════════════════════════════════════════════════════════

/** Render epoch seconds as ``YYYY-MM-DD`` in Asia/Kolkata so we can
 *  group bars by IST trading date. */
function istDateKey(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1_000);
  // ``en-CA`` locale yields ISO ``YYYY-MM-DD`` ordering — perfect
  // for string equality comparison without parsing back.
  return d.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
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

function formatSignedDelta(value: number): string {
  const sign = value >= 0 ? "+" : "−"; // unicode minus for kerning
  return `${sign}${formatPrice(Math.abs(value))}`;
}

function formatSignedPct(value: number): string {
  const sign = value >= 0 ? "+" : "−";
  return `${sign}${Math.abs(value).toFixed(2)}%`;
}

// ═══════════════════════════════════════════════════════════════════════
// Pure derivation (exported for unit testing without DOM)
// ═══════════════════════════════════════════════════════════════════════

export interface DerivedHeaderInfo {
  /** Last close. ``null`` if the candles array is empty. */
  price: number | null;
  /** First today-bar's open — baseline for the change calc. */
  open: number | null;
  /** Max high across today's bars. */
  high: number | null;
  /** Min low across today's bars. */
  low: number | null;
  /** Sum of volume across today's bars. */
  volume: number;
  /** ``price - open``. ``null`` if either is missing. */
  absChange: number | null;
  /** ``(price / open - 1) * 100``. ``null`` if open ≤ 0. */
  pctChange: number | null;
  /** Convenience: ``true`` when the day is in the green. ``null``
   *  when there's no change to compute. */
  isUp: boolean | null;
}

export function deriveHeaderInfo(candles: Candle[]): DerivedHeaderInfo {
  if (candles.length === 0) {
    return {
      price: null,
      open: null,
      high: null,
      low: null,
      volume: 0,
      absChange: null,
      pctChange: null,
      isUp: null,
    };
  }
  const last = candles[candles.length - 1];
  const todayKey = istDateKey(last.time);
  // Walk from the tail backward — today's bars are contiguous at
  // the end of the (time-sorted) array. Stop at the first bar
  // whose IST date differs.
  let cutoff = candles.length;
  for (let i = candles.length - 1; i >= 0; i--) {
    if (istDateKey(candles[i].time) !== todayKey) {
      cutoff = i + 1;
      break;
    }
    if (i === 0) cutoff = 0;
  }
  const todayBars =
    cutoff < candles.length ? candles.slice(cutoff) : candles;

  const open = todayBars[0].open;
  let high = todayBars[0].high;
  let low = todayBars[0].low;
  let volume = 0;
  for (const b of todayBars) {
    if (b.high > high) high = b.high;
    if (b.low < low) low = b.low;
    volume += b.volume;
  }
  const price = last.close;
  const absChange = price - open;
  const pctChange = open > 0 ? (absChange / open) * 100 : null;
  return {
    price,
    open,
    high,
    low,
    volume,
    absChange,
    pctChange,
    isUp: absChange === 0 ? null : absChange > 0,
  };
}

// ═══════════════════════════════════════════════════════════════════════
// Component
// ═══════════════════════════════════════════════════════════════════════

export interface ChartHeaderInfoProps {
  symbol: string;
  candles: Candle[];
}

export function ChartHeaderInfo({ symbol, candles }: ChartHeaderInfoProps) {
  const info = useMemo(() => deriveHeaderInfo(candles), [candles]);

  if (info.price === null) {
    return (
      <div
        data-testid="chart-header-info"
        data-state="empty"
        className="flex items-center gap-2 px-1 text-xs text-neutral-400"
      >
        <span className="font-semibold uppercase tracking-wide text-neutral-300">
          {symbol}
        </span>
        <span>—</span>
      </div>
    );
  }

  // ``isUp === null`` (zero change) renders neutral-200; otherwise
  // green-500 / red-400 mirror the candle palette.
  const accentClass =
    info.isUp === null
      ? "text-neutral-200"
      : info.isUp
        ? "text-green-500"
        : "text-red-400";

  return (
    <div
      data-testid="chart-header-info"
      data-state="loaded"
      data-direction={
        info.isUp === null ? "flat" : info.isUp ? "up" : "down"
      }
      className="flex flex-wrap items-baseline gap-x-4 gap-y-1 px-1 text-xs text-neutral-300"
    >
      <span className="font-semibold uppercase tracking-wide text-neutral-200">
        {symbol}
      </span>

      {/* Mobile-essential pair: price + percentage change.
          Always visible. */}
      <span
        className={`text-lg font-bold tabular-nums ${accentClass}`}
        data-testid="header-price"
      >
        ₹{formatPrice(info.price)}
      </span>
      {info.absChange !== null && info.pctChange !== null && (
        <span
          className={`tabular-nums ${accentClass}`}
          data-testid="header-change"
        >
          {formatSignedDelta(info.absChange)}{" "}
          ({formatSignedPct(info.pctChange)})
        </span>
      )}

      {/* Desktop-only OHLCV breakdown. Hidden under sm: because
          it crowds narrow phone viewports — the chart canvas is
          the priority there. */}
      <span
        className="hidden items-baseline gap-3 sm:inline-flex"
        data-testid="header-ohlcv"
      >
        <span className="text-neutral-400">
          O <span className="text-neutral-200 tabular-nums">{formatPrice(info.open!)}</span>
        </span>
        <span className="text-neutral-400">
          H <span className="text-neutral-200 tabular-nums">{formatPrice(info.high!)}</span>
        </span>
        <span className="text-neutral-400">
          L <span className="text-neutral-200 tabular-nums">{formatPrice(info.low!)}</span>
        </span>
        <span className="text-neutral-400">
          V <span className="text-neutral-200 tabular-nums">{formatVolume(info.volume)}</span>
        </span>
      </span>
    </div>
  );
}
