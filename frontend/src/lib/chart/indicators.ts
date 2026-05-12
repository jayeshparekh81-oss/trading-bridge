/**
 * Indicator computations — pure helpers used by the chart's
 * indicator overlay (SMA20, EMA50, RSI, MACD).
 *
 * All functions operate on epoch-second-keyed candle arrays and
 * return line / histogram point arrays in the Lightweight Charts
 * shape so the consumer can ``series.setData(...)`` directly.
 *
 * Numerically stable + boring: no external math library, no
 * floating-point trickery beyond what a textbook indicator
 * implementation requires. Phase-2 / Phase-3 / Phase-N indicator
 * sprints will replace these with backend-fed series, but until
 * then the client-side compute keeps the UI testable + offline-
 * capable in mock mode.
 */

import type { Candle } from "./types";

export interface LinePoint {
  time: number;
  value: number;
}

export interface HistogramPoint {
  time: number;
  value: number;
  color?: string;
}

// ─── Simple Moving Average ────────────────────────────────────────────

/**
 * SMA(N) — arithmetic mean of the last N closes. Output starts at
 * index ``period - 1`` (the first window where the average is
 * defined); earlier indices are dropped from the output rather than
 * emitted as ``NaN``.
 */
export function computeSMA(candles: Candle[], period: number): LinePoint[] {
  if (period <= 0) throw new Error("computeSMA: period must be > 0");
  if (candles.length < period) return [];
  const out: LinePoint[] = [];
  let runningSum = 0;
  for (let i = 0; i < period; i++) runningSum += candles[i].close;
  out.push({ time: candles[period - 1].time, value: runningSum / period });
  for (let i = period; i < candles.length; i++) {
    runningSum += candles[i].close - candles[i - period].close;
    out.push({ time: candles[i].time, value: runningSum / period });
  }
  return out;
}

// ─── Exponential Moving Average ───────────────────────────────────────

/**
 * EMA(N) — recursive exponential smoothing seeded with the SMA of
 * the first N closes. Smoothing factor ``α = 2 / (N + 1)``. Output
 * starts at index ``period - 1`` (same alignment as SMA).
 */
export function computeEMA(candles: Candle[], period: number): LinePoint[] {
  if (period <= 0) throw new Error("computeEMA: period must be > 0");
  if (candles.length < period) return [];
  const out: LinePoint[] = [];
  const alpha = 2 / (period + 1);
  // Seed with the SMA so the first emitted point is consistent with
  // computeSMA's first point.
  let seed = 0;
  for (let i = 0; i < period; i++) seed += candles[i].close;
  seed /= period;
  let prev = seed;
  out.push({ time: candles[period - 1].time, value: seed });
  for (let i = period; i < candles.length; i++) {
    prev = candles[i].close * alpha + prev * (1 - alpha);
    out.push({ time: candles[i].time, value: prev });
  }
  return out;
}

// ─── Relative Strength Index ──────────────────────────────────────────

/**
 * RSI(N) — Wilder's RSI. Computes average gain / average loss over
 * the last N periods, then ``RSI = 100 - 100/(1 + RS)`` where
 * ``RS = avgGain / avgLoss``. Output starts at index ``period``
 * (the first window with N completed price changes).
 *
 * Edge case: when ``avgLoss == 0`` the formal definition is RSI=100;
 * that's what we emit (no NaN).
 */
export function computeRSI(candles: Candle[], period = 14): LinePoint[] {
  if (period <= 0) throw new Error("computeRSI: period must be > 0");
  if (candles.length <= period) return [];
  const out: LinePoint[] = [];
  let gainSum = 0;
  let lossSum = 0;
  for (let i = 1; i <= period; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    if (diff > 0) gainSum += diff;
    else lossSum -= diff;
  }
  let avgGain = gainSum / period;
  let avgLoss = lossSum / period;
  out.push({
    time: candles[period].time,
    value: avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss),
  });
  for (let i = period + 1; i < candles.length; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? -diff : 0;
    // Wilder smoothing — equivalent to EMA with α = 1/period.
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    out.push({
      time: candles[i].time,
      value: avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss),
    });
  }
  return out;
}

// ─── MACD ─────────────────────────────────────────────────────────────

export interface MACDPoint {
  time: number;
  macd: number;
  signal: number;
  histogram: number;
}

/**
 * MACD with the standard (12, 26, 9) periods unless overridden.
 * Returns one combined point array; consumers split into three
 * series on the LWC side (line / line / histogram).
 *
 * Output alignment: starts at ``slow + signal - 1`` so the signal
 * line is fully defined for every emitted point.
 */
export function computeMACD(
  candles: Candle[],
  fast = 12,
  slow = 26,
  signal = 9,
): MACDPoint[] {
  if (fast <= 0 || slow <= 0 || signal <= 0) {
    throw new Error("computeMACD: all periods must be > 0");
  }
  if (slow <= fast) {
    throw new Error("computeMACD: slow must be > fast");
  }
  if (candles.length < slow + signal - 1) return [];

  const fastEma = computeEMA(candles, fast);
  const slowEma = computeEMA(candles, slow);
  // Align the two EMAs on shared timestamps. SMA-seeded EMAs above
  // start at index period-1 each; slow starts later than fast so
  // we trim the head of fast.
  const offset = slow - fast;
  const macdLine: LinePoint[] = [];
  for (let i = 0; i < slowEma.length; i++) {
    macdLine.push({
      time: slowEma[i].time,
      value: fastEma[i + offset].value - slowEma[i].value,
    });
  }
  // Signal line = EMA(signal) of the macd line. We re-implement
  // the EMA against a LinePoint[] rather than reusing computeEMA
  // (which expects Candle[]) — keeps the helper public surface
  // candle-only.
  const alpha = 2 / (signal + 1);
  let seed = 0;
  for (let i = 0; i < signal; i++) seed += macdLine[i].value;
  seed /= signal;
  const signalLine: LinePoint[] = [
    { time: macdLine[signal - 1].time, value: seed },
  ];
  let prev = seed;
  for (let i = signal; i < macdLine.length; i++) {
    prev = macdLine[i].value * alpha + prev * (1 - alpha);
    signalLine.push({ time: macdLine[i].time, value: prev });
  }
  // Stitch into combined points starting at signal-1.
  const out: MACDPoint[] = [];
  for (let i = 0; i < signalLine.length; i++) {
    const macdVal = macdLine[i + signal - 1].value;
    const sigVal = signalLine[i].value;
    out.push({
      time: signalLine[i].time,
      macd: macdVal,
      signal: sigVal,
      histogram: macdVal - sigVal,
    });
  }
  return out;
}
