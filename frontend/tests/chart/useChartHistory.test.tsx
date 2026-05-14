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
});
