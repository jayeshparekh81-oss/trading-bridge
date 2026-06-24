import { describe, it, expect } from "vitest";
import {
  DEFAULT_RANGE,
  RANGE_OPTIONS,
  rangeMonths,
  rebaseToWindow,
} from "@/lib/showcase/range";
import type { SeriesPoint } from "@/lib/showcase/data";

// Cumulative non-compounded series (v = running sum of per-trade NET %).
// per-trade %s:        +10    +15    +15    +5
const SERIES: SeriesPoint[] = [
  { d: "2025-12-01", v: 10 },
  { d: "2026-02-01", v: 25 },
  { d: "2026-04-01", v: 40 },
  { d: "2026-05-01", v: 55 },
  { d: "2026-06-18", v: 60 }, // series' own latest date
];

describe("range options", () => {
  it("defaults to 3M", () => {
    expect(DEFAULT_RANGE).toBe("3M");
  });
  it("offers 1M…5Y + All", () => {
    expect(RANGE_OPTIONS.map((o) => o.v)).toEqual([
      "1M", "3M", "6M", "1Y", "2Y", "3Y", "4Y", "5Y", "All",
    ]);
    expect(rangeMonths("3M")).toBe(3);
    expect(rangeMonths("All")).toBeNull();
  });
});

describe("rebaseToWindow", () => {
  it("3M window: starts at 0% and ends at the SUM of the window's per-trade %s", () => {
    // window from 2026-06-18 back 3 months = 2026-03-18 → in-window: 04-01,05-01,06-18
    const out = rebaseToWindow(SERIES, 3);
    expect(out[0].value).toBe(0); // re-based: window starts at 0%
    expect(out[out.length - 1].value).toBe(35); // 15 + 15 + 5 (NOT the full +60)
    // anchor at the pre-window point's date + the 3 in-window points
    expect(out.map((p) => p.time)).toEqual([
      "2026-02-01", "2026-04-01", "2026-05-01", "2026-06-18",
    ]);
    expect(out.map((p) => p.value)).toEqual([0, 15, 30, 35]);
  });

  it("6M window re-bases against its own baseline (last = +50, not +60)", () => {
    const out = rebaseToWindow(SERIES, 6); // start 2025-12-18 → predecessor 2025-12-01 (v=10)
    expect(out[0].value).toBe(0);
    expect(out[out.length - 1].value).toBe(50); // 60 − 10
  });

  it("1M window: only the last trade, re-based from 0", () => {
    const out = rebaseToWindow(SERIES, 1); // start 2026-05-18 → predecessor 2026-05-01 (v=55)
    expect(out.map((p) => p.value)).toEqual([0, 5]); // 60 − 55
  });

  it("All: full series as-is (cumulative from the first trade)", () => {
    const out = rebaseToWindow(SERIES, null);
    expect(out).toHaveLength(SERIES.length);
    expect(out[0]).toEqual({ time: "2025-12-01", value: 10 });
    expect(out[out.length - 1]).toEqual({ time: "2026-06-18", value: 60 });
  });

  it("a window covering the whole series starts at the first trade (no negative baseline)", () => {
    const out = rebaseToWindow(SERIES, 120); // 10Y ⊃ whole 6-month series
    expect(out).toHaveLength(SERIES.length); // no prepended anchor
    expect(out[0].value).toBe(10);
    expect(out[out.length - 1].value).toBe(60);
  });

  it("empty series → empty", () => {
    expect(rebaseToWindow([], 3)).toEqual([]);
  });

  it("never invents points — output length ≤ series + 1 anchor", () => {
    for (const o of RANGE_OPTIONS) {
      const out = rebaseToWindow(SERIES, o.months);
      expect(out.length).toBeLessThanOrEqual(SERIES.length + 1);
    }
  });
});
