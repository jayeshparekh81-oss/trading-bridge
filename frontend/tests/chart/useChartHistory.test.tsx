import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/chart/api", () => ({
  fetchChartHistory: vi.fn(),
}));

import { fetchChartHistory } from "@/lib/chart/api";
import { useChartHistory } from "@/hooks/useChartHistory";
import { getMockHistory } from "@/lib/chart/mock_data";

const mockedFetch = vi.mocked(fetchChartHistory);

describe("useChartHistory", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("loads candles on mount", async () => {
    mockedFetch.mockResolvedValue(
      getMockHistory({ symbol: "NIFTY", timeframe: "5m", length: 50 }),
    );
    const { result } = renderHook(() =>
      useChartHistory({
        symbol: "NIFTY",
        exchange: "NSE",
        timeframe: "5m",
      }),
    );
    expect(result.current.isLoading).toBe(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.candles).toHaveLength(50);
    expect(result.current.candles[0].time).toBeLessThan(
      result.current.candles[49].time,
    );
    expect(result.current.error).toBeNull();
  });

  it("captures fetch errors", async () => {
    mockedFetch.mockRejectedValue(new Error("network"));
    const { result } = renderHook(() =>
      useChartHistory({
        symbol: "NIFTY",
        exchange: "NSE",
        timeframe: "5m",
      }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.error?.message).toBe("network");
    expect(result.current.candles).toEqual([]);
  });

  it("refetch re-issues the request", async () => {
    mockedFetch.mockResolvedValue(
      getMockHistory({ symbol: "NIFTY", timeframe: "5m", length: 10 }),
    );
    const { result } = renderHook(() =>
      useChartHistory({
        symbol: "NIFTY",
        exchange: "NSE",
        timeframe: "5m",
      }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(mockedFetch).toHaveBeenCalledTimes(1);
    await act(async () => {
      result.current.refetch();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(mockedFetch).toHaveBeenCalledTimes(2);
  });

  it("symbol change triggers re-fetch", async () => {
    mockedFetch.mockResolvedValue(
      getMockHistory({ symbol: "NIFTY", timeframe: "5m", length: 5 }),
    );
    const { rerender } = renderHook(
      ({ symbol }: { symbol: string }) =>
        useChartHistory({
          symbol,
          exchange: "NSE",
          timeframe: "5m",
        }),
      { initialProps: { symbol: "NIFTY" } },
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(mockedFetch).toHaveBeenCalledTimes(1);
    rerender({ symbol: "BANKNIFTY" });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(mockedFetch).toHaveBeenCalledTimes(2);
  });

  it("enabled=false skips the fetch and flips loading to false", async () => {
    const { result } = renderHook(() =>
      useChartHistory({
        symbol: "NIFTY",
        exchange: "NSE",
        timeframe: "5m",
        enabled: false,
      }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(mockedFetch).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.candles).toEqual([]);
  });

  it("wraps non-Error throwables", async () => {
    mockedFetch.mockRejectedValue("string failure");
    const { result } = renderHook(() =>
      useChartHistory({
        symbol: "NIFTY",
        exchange: "NSE",
        timeframe: "5m",
      }),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe("history fetch failed");
  });

  // ── Calendar-aware window (5m blank-on-weekend fix) ────────────────
  // The lookback window is clamped to [7 days, 60 days]. Without the
  // floor, a 200-bar 5m window covers only ~16.7h — too short to reach
  // back to Friday's last bar on a Sunday afternoon, so the chart
  // renders empty. With the floor, the request window always covers
  // at least the most recent trading session.
  describe("calendar-aware history window", () => {
    function spanDays(fromIso: string, toIso: string): number {
      return (
        (new Date(toIso).getTime() - new Date(fromIso).getTime()) /
        (86400 * 1000)
      );
    }

    it("5m timeframe uses 7-day floor when market closed", async () => {
      mockedFetch.mockResolvedValue(
        getMockHistory({ symbol: "NIFTY", timeframe: "5m", length: 0 }),
      );
      renderHook(() =>
        useChartHistory({
          symbol: "NIFTY",
          exchange: "NSE",
          timeframe: "5m",
        }),
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockedFetch).toHaveBeenCalledTimes(1);
      const args = mockedFetch.mock.calls[0][0];
      // Naïve 5m × 200 = 16.7h ≈ 0.7 days. With the 7-day floor, the
      // window must span at least 7 days. Exact equality (not >=) because
      // 7d > 0.7d so the floor wins; any deviation would indicate the
      // floor was bypassed.
      expect(spanDays(args.from, args.to)).toBeCloseTo(7, 6);
    });

    it("1d timeframe uses natural window unchanged (15-day window > 7-day floor)", async () => {
      mockedFetch.mockResolvedValue(
        getMockHistory({ symbol: "NIFTY", timeframe: "1d", length: 0 }),
      );
      renderHook(() =>
        useChartHistory({
          symbol: "NIFTY",
          exchange: "NSE",
          timeframe: "1d",
          barCount: 15,
        }),
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockedFetch).toHaveBeenCalledTimes(1);
      const args = mockedFetch.mock.calls[0][0];
      // 1d × 15 bars = 15 days, which exceeds the 7-day floor, so the
      // natural window wins. Capped at 60d but 15 < 60, so no cap.
      expect(spanDays(args.from, args.to)).toBeCloseTo(15, 6);
    });

    it("window capped at 60 days even when natural window exceeds it", async () => {
      mockedFetch.mockResolvedValue(
        getMockHistory({ symbol: "NIFTY", timeframe: "1d", length: 0 }),
      );
      renderHook(() =>
        useChartHistory({
          symbol: "NIFTY",
          exchange: "NSE",
          timeframe: "1d",
          // 1d × 200 = 200 days, exceeds the 60-day cap.
          barCount: 200,
        }),
      );
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockedFetch).toHaveBeenCalledTimes(1);
      const args = mockedFetch.mock.calls[0][0];
      expect(spanDays(args.from, args.to)).toBeCloseTo(60, 6);
    });
  });
});
