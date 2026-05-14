/**
 * useChartScrollback — Phase 5 hook tests.
 *
 * The hook owns the older-bars buffer + in-flight gating + 5-year
 * cap for intraday timeframes. Tests use ``forceMock=true`` so the
 * hook routes through ``getMockOlderHistory`` (no MSW needed) and
 * the buffer dynamics can be exercised end-to-end.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useChartScrollback } from "@/hooks/useChartScrollback";

// ─── Helpers ───────────────────────────────────────────────────────────

const baseOpts = {
  symbol: "NIFTY",
  exchange: "NSE" as const,
  timeframe: "5m" as const,
  forceMock: true,
};

beforeEach(() => {
  vi.useRealTimers();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useChartScrollback — initial state", () => {
  it("starts with empty buffer + idle flags", () => {
    const { result } = renderHook(() => useChartScrollback(baseOpts));
    expect(result.current.olderCandles).toEqual([]);
    expect(result.current.isLoadingOlder).toBe(false);
    expect(result.current.hasReachedCap).toBe(false);
    expect(result.current.error).toBeNull();
  });
});

describe("useChartScrollback — requestOlder happy path", () => {
  it("populates olderCandles after a successful fetch", async () => {
    const { result } = renderHook(() =>
      useChartScrollback({ ...baseOpts, barCount: 50 }),
    );

    act(() => {
      result.current.requestOlder(1_800_000_000);
    });
    // isLoadingOlder is set synchronously inside the call site.
    expect(result.current.isLoadingOlder).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });
    expect(result.current.olderCandles).toHaveLength(50);
    // Returned bars are sorted ascending by time.
    for (let i = 1; i < result.current.olderCandles.length; i++) {
      expect(result.current.olderCandles[i].time).toBeGreaterThan(
        result.current.olderCandles[i - 1].time,
      );
    }
  });

  it("PREPENDS additional fetches (older end of the buffer)", async () => {
    const { result } = renderHook(() =>
      useChartScrollback({ ...baseOpts, barCount: 20 }),
    );

    act(() => result.current.requestOlder(1_800_000_000));
    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });
    const firstBatchEarliest = result.current.olderCandles[0].time;

    act(() => result.current.requestOlder(firstBatchEarliest));
    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });

    expect(result.current.olderCandles).toHaveLength(40);
    // Newly-prepended bars are strictly older than the first batch
    // and contiguous (no gap, no overlap).
    expect(result.current.olderCandles[19].time).toBeLessThan(
      firstBatchEarliest,
    );
    // Continuity: 19th element + tfSeconds === firstBatchEarliest.
    expect(firstBatchEarliest - result.current.olderCandles[19].time).toBe(
      300,
    );
  });
});

describe("useChartScrollback — gating", () => {
  it("requestOlder is a no-op while isLoadingOlder is true (concurrent fast-scroll guard)", async () => {
    const { result } = renderHook(() =>
      useChartScrollback({ ...baseOpts, barCount: 30 }),
    );

    act(() => {
      result.current.requestOlder(1_800_000_000);
      // Second fire while the first is in flight — must be a no-op.
      result.current.requestOlder(1_800_000_000 - 10_000);
    });

    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });
    // Only the FIRST fetch should have committed bars.
    expect(result.current.olderCandles).toHaveLength(30);
  });

  it("flips hasReachedCap once cumulative scroll-back exceeds 5 years on intraday", async () => {
    const { result } = renderHook(() =>
      useChartScrollback({ ...baseOpts, barCount: 10 }),
    );
    const anchor = 1_800_000_000;
    const sixYearsSec = 6 * 365 * 24 * 60 * 60;

    act(() => result.current.requestOlder(anchor));
    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });

    // Now request a beforeEpoch that is 6 years prior to the anchor.
    act(() => result.current.requestOlder(anchor - sixYearsSec));
    expect(result.current.hasReachedCap).toBe(true);
    // Subsequent requests are also no-ops.
    act(() => result.current.requestOlder(anchor - sixYearsSec - 1_000));
    expect(result.current.olderCandles).toHaveLength(10);
  });

  it("does NOT cap daily timeframe (only intraday)", async () => {
    const { result } = renderHook(() =>
      useChartScrollback({ ...baseOpts, timeframe: "1d", barCount: 5 }),
    );
    const anchor = 1_800_000_000;
    const tenYearsSec = 10 * 365 * 24 * 60 * 60;

    act(() => result.current.requestOlder(anchor));
    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });
    act(() => result.current.requestOlder(anchor - tenYearsSec));
    expect(result.current.hasReachedCap).toBe(false);
    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });
    expect(result.current.olderCandles).toHaveLength(10);
  });
});

describe("useChartScrollback — symbol/timeframe reset", () => {
  it("clears the buffer when symbol changes", async () => {
    const { result, rerender } = renderHook(
      (props: typeof baseOpts) => useChartScrollback(props),
      { initialProps: { ...baseOpts, barCount: 25 } },
    );

    act(() => result.current.requestOlder(1_800_000_000));
    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });
    expect(result.current.olderCandles).toHaveLength(25);

    rerender({ ...baseOpts, barCount: 25, symbol: "BANKNIFTY" });
    expect(result.current.olderCandles).toEqual([]);
    expect(result.current.hasReachedCap).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("clears the buffer when timeframe changes", async () => {
    const { result, rerender } = renderHook(
      (props: typeof baseOpts) => useChartScrollback(props),
      { initialProps: { ...baseOpts, barCount: 25 } },
    );

    act(() => result.current.requestOlder(1_800_000_000));
    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });

    rerender({ ...baseOpts, barCount: 25, timeframe: "15m" });
    expect(result.current.olderCandles).toEqual([]);
  });
});

describe("useChartScrollback — manual reset", () => {
  it("reset() clears the buffer + flags", async () => {
    const { result } = renderHook(() =>
      useChartScrollback({ ...baseOpts, barCount: 10 }),
    );

    act(() => result.current.requestOlder(1_800_000_000));
    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });
    expect(result.current.olderCandles).toHaveLength(10);

    act(() => result.current.reset());
    expect(result.current.olderCandles).toEqual([]);
    expect(result.current.isLoadingOlder).toBe(false);
    expect(result.current.hasReachedCap).toBe(false);
    expect(result.current.error).toBeNull();
  });
});

// ─── Module-mocked branches: empty fetch + fetch failure ───────────────
//
// The default forceMock path always returns ``barCount`` synthetic
// bars, so the empty-response and error-path branches need an
// explicit module mock to exercise them. Kept in a separate ``describe``
// so the mock is scoped via ``vi.doMock`` and doesn't bleed into the
// happy-path tests above.

describe("useChartScrollback — module-mocked branches", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("empty fetch response flips hasReachedCap (backend has nothing further)", async () => {
    vi.doMock("@/lib/chart/api", () => ({
      fetchOlderHistory: vi.fn().mockResolvedValue({
        symbol: "NIFTY",
        timeframe: "5m",
        from_ts: "",
        to_ts: "",
        cached: false,
        candles: [],
      }),
    }));

    const { useChartScrollback: hook } = await import(
      "@/hooks/useChartScrollback"
    );
    const { result } = renderHook(() =>
      hook({ symbol: "NIFTY", exchange: "NSE", timeframe: "5m" }),
    );

    act(() => result.current.requestOlder(1_800_000_000));
    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });

    expect(result.current.hasReachedCap).toBe(true);
    expect(result.current.olderCandles).toEqual([]);
  });

  it("fetch failure sets error and does NOT flip the cap", async () => {
    vi.doMock("@/lib/chart/api", () => ({
      fetchOlderHistory: vi
        .fn()
        .mockRejectedValue(new Error("network down")),
    }));

    const { useChartScrollback: hook } = await import(
      "@/hooks/useChartScrollback"
    );
    const { result } = renderHook(() =>
      hook({ symbol: "NIFTY", exchange: "NSE", timeframe: "5m" }),
    );

    act(() => result.current.requestOlder(1_800_000_000));
    await waitFor(() => {
      expect(result.current.isLoadingOlder).toBe(false);
    });

    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe("network down");
    expect(result.current.hasReachedCap).toBe(false);
    expect(result.current.olderCandles).toEqual([]);
  });

  it("non-Error thrown value is wrapped in a generic Error", async () => {
    vi.doMock("@/lib/chart/api", () => ({
      fetchOlderHistory: vi.fn().mockRejectedValue("plain string"),
    }));

    const { useChartScrollback: hook } = await import(
      "@/hooks/useChartScrollback"
    );
    const { result } = renderHook(() =>
      hook({ symbol: "NIFTY", exchange: "NSE", timeframe: "5m" }),
    );

    act(() => result.current.requestOlder(1_800_000_000));
    await waitFor(() => {
      expect(result.current.error).not.toBeNull();
    });
    expect(result.current.error?.message).toMatch(
      /older-history fetch failed/i,
    );
  });
});
