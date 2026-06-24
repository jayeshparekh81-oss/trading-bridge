/**
 * Equity-curve time-range selection + re-basing for the showcase chart.
 *
 * The non-compounded series (``equity_curve_noncompounded``) is a running SUM of
 * per-trade NET %: point ``i`` holds the cumulative % through trade ``i``. The
 * full series spans 2019→2026, so showing it whole reads as a huge number that
 * dwarfs recent behaviour. A range selector lets the viewer read each window on
 * its own, RE-BASED so the window starts at 0%.
 *
 * Re-basing: subtract the cumulative value just BEFORE the window (its baseline)
 * from every in-window point, and prepend a 0% anchor at the window start. Then
 * the curve reads "+X% over the last N months" from 0 — the last point equals
 * the SUM of that window's per-trade %s (cumulative_end − baseline), not the
 * full-series figure (e.g. +1700%).
 *
 * NOTE: the window is computed from the SERIES' own latest date (the backtest
 * ends ~2026-06-18/19), not today's date — so 3M/6M always show data.
 *
 * Pure, frontend-only. No backend / endpoint / mutation.
 */

import type { SeriesPoint } from "@/lib/showcase/data";

export interface RangeOption {
  v: RangeKey;
  /** Window length in months; ``null`` = the full series ("All"). */
  months: number | null;
}

export const RANGE_OPTIONS = [
  { v: "1M", months: 1 },
  { v: "3M", months: 3 },
  { v: "6M", months: 6 },
  { v: "1Y", months: 12 },
  { v: "2Y", months: 24 },
  { v: "3Y", months: 36 },
  { v: "4Y", months: 48 },
  { v: "5Y", months: 60 },
  { v: "All", months: null },
] as const satisfies readonly { v: string; months: number | null }[];

export type RangeKey = (typeof RANGE_OPTIONS)[number]["v"];

/** Default range — recent, readable, not the overwhelming full series. */
export const DEFAULT_RANGE: RangeKey = "3M";

const _MONTHS: Record<RangeKey, number | null> = Object.fromEntries(
  RANGE_OPTIONS.map((o) => [o.v, o.months]),
) as Record<RangeKey, number | null>;

export function rangeMonths(key: RangeKey): number | null {
  return _MONTHS[key];
}

export interface ChartPoint {
  time: string;
  value: number;
}

/**
 * Filter ``points`` (sorted ascending by date) to the last ``months`` from the
 * series' OWN latest date, then re-base so the window starts at 0%.
 *
 *  * ``months === null`` ("All") → the full series as-is (cumulative from the
 *    first trade).
 *  * Otherwise → every in-window point minus the pre-window baseline, with a
 *    leading ``value: 0`` anchor. First point = 0%; last point = the SUM of the
 *    window's per-trade %s. When the window covers the whole available series
 *    (no pre-window point) it simply starts at the first trade's cumulative.
 */
export function rebaseToWindow(
  points: readonly SeriesPoint[],
  months: number | null,
): ChartPoint[] {
  if (points.length === 0) return [];
  if (months == null) {
    return points.map((p) => ({ time: p.d, value: p.v }));
  }

  const lastMs = Date.parse(points[points.length - 1].d);
  const start = new Date(lastMs);
  start.setMonth(start.getMonth() - months);
  const startMs = start.getTime();

  const firstIdx = points.findIndex((p) => Date.parse(p.d) >= startMs);
  if (firstIdx === -1) return []; // nothing in the window

  const inWindow = points.slice(firstIdx);
  const baseline = firstIdx > 0 ? points[firstIdx - 1].v : 0;
  const rebased = inWindow.map((p) => ({ time: p.d, value: p.v - baseline }));

  // A pre-window point exists → anchor the curve at 0% on its date so the
  // window reads from 0. If the window covers the series start, the series
  // already begins at the first trade's cumulative (nothing to anchor to).
  if (firstIdx > 0) {
    return [{ time: points[firstIdx - 1].d, value: 0 }, ...rebased];
  }
  return rebased;
}
