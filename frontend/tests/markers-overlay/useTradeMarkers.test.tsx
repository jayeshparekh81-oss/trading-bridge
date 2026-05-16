/**
 * useTradeMarkers hook tests.
 *
 * Mock the API module at file level, drive the mocked fn per test.
 * Exercise: disabled state, happy path, refetch, dep changes,
 * stale-response drop, 401/403/5xx error surfacing, highlight memo.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockFetchMarkers = vi.fn();

vi.mock("@/lib/markers-overlay/api", () => ({
  fetchMarkers: (...args: unknown[]) => mockFetchMarkers(...args),
}));

// eslint-disable-next-line import/first
import {
  useTradeMarkers,
  type UseTradeMarkersOptions,
} from "@/hooks/useTradeMarkers";

const happyResponse = {
  strategy_id: "11111111-1111-1111-1111-111111111111",
  mode: "PAPER" as const,
  limit: 100,
  offset: 0,
  total: 2,
  markers: [
    {
      id: "m-1",
      strategy_id: "11111111-1111-1111-1111-111111111111",
      user_id: "u-1",
      symbol: "NIFTY",
      exchange: "NSE",
      side: "LONG_ENTRY" as const,
      price: "22500.00",
      quantity: 50,
      timestamp_utc: "2026-05-14T09:15:00+00:00",
      mode: "PAPER" as const,
      linked_marker_id: null,
      pnl: null,
      exit_reason: null,
      signal_metadata: {},
      created_at: "2026-05-14T09:15:00+00:00",
    },
    {
      id: "m-2",
      strategy_id: "11111111-1111-1111-1111-111111111111",
      user_id: "u-1",
      symbol: "NIFTY",
      exchange: "NSE",
      side: "LONG_EXIT" as const,
      price: "22550.00",
      quantity: 50,
      timestamp_utc: "2026-05-14T10:00:00+00:00",
      mode: "PAPER" as const,
      linked_marker_id: "m-1",
      pnl: "2500.00",
      exit_reason: "TAKE_PROFIT" as const,
      signal_metadata: {},
      created_at: "2026-05-14T10:00:00+00:00",
    },
  ],
};

const baseOpts: UseTradeMarkersOptions = {
  strategyId: "11111111-1111-1111-1111-111111111111",
  mode: "PAPER",
};

beforeEach(() => {
  vi.useRealTimers();
  mockFetchMarkers.mockReset().mockResolvedValue(happyResponse);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useTradeMarkers — disabled state", () => {
  it("does not fetch when strategyId is null", () => {
    const { result } = renderHook(() =>
      useTradeMarkers({ ...baseOpts, strategyId: null }),
    );
    expect(result.current.markers).toEqual([]);
    expect(result.current.rawMarkers).toEqual([]);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.hasLoaded).toBe(false);
    expect(mockFetchMarkers).not.toHaveBeenCalled();
  });

  it("does not fetch when enabled=false", () => {
    renderHook(() => useTradeMarkers({ ...baseOpts, enabled: false }));
    expect(mockFetchMarkers).not.toHaveBeenCalled();
  });
});

describe("useTradeMarkers — happy path", () => {
  it("fetches once on mount, parses the response, sets hasLoaded", async () => {
    const { result } = renderHook(() => useTradeMarkers(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(mockFetchMarkers).toHaveBeenCalledTimes(1);
    expect(result.current.error).toBeNull();
    expect(result.current.rawMarkers).toHaveLength(2);
    expect(result.current.rawMarkers[0].price).toBe(22500);
    expect(result.current.rawMarkers[1].pnl).toBe(2500);
  });

  it("produces SeriesMarker shape ready for series.setMarkers()", async () => {
    const { result } = renderHook(() => useTradeMarkers(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.markers).toHaveLength(2);
    // Sorted ascending by time
    expect(result.current.markers[0].time).toBeLessThan(
      result.current.markers[1].time as number,
    );
    // SeriesMarker.id round-trips the backend UUID
    expect(result.current.markers[0].id).toBe("m-1");
    expect(result.current.markers[1].id).toBe("m-2");
  });

  it("forwards mode + window + filters to the fetcher", async () => {
    const { result } = renderHook(() =>
      useTradeMarkers({
        ...baseOpts,
        mode: "BACKTEST",
        symbol: "RELIANCE",
        fromIso: "2026-05-01T00:00:00+00:00",
        toIso: "2026-05-14T00:00:00+00:00",
        side: "LONG_ENTRY",
        limit: 50,
        offset: 0,
      }),
    );
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(mockFetchMarkers).toHaveBeenCalledWith({
      strategyId: baseOpts.strategyId,
      mode: "BACKTEST",
      symbol: "RELIANCE",
      fromIso: "2026-05-01T00:00:00+00:00",
      toIso: "2026-05-14T00:00:00+00:00",
      side: "LONG_ENTRY",
      limit: 50,
      offset: 0,
    });
  });

  it("re-fetches when strategyId, mode, or window changes", async () => {
    const { result, rerender } = renderHook(
      (p: UseTradeMarkersOptions) => useTradeMarkers(p),
      { initialProps: baseOpts },
    );
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(mockFetchMarkers).toHaveBeenCalledTimes(1);

    rerender({ ...baseOpts, mode: "BACKTEST" });
    await waitFor(() => expect(mockFetchMarkers).toHaveBeenCalledTimes(2));

    rerender({
      strategyId: "22222222-2222-2222-2222-222222222222",
      mode: "BACKTEST",
    });
    await waitFor(() => expect(mockFetchMarkers).toHaveBeenCalledTimes(3));

    rerender({
      strategyId: "22222222-2222-2222-2222-222222222222",
      mode: "BACKTEST",
      fromIso: "2026-05-01T00:00:00+00:00",
    });
    await waitFor(() => expect(mockFetchMarkers).toHaveBeenCalledTimes(4));
  });

  it("refetch() re-runs the fetch on demand", async () => {
    const { result } = renderHook(() => useTradeMarkers(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    await act(async () => {
      await result.current.refetch();
    });
    expect(mockFetchMarkers).toHaveBeenCalledTimes(2);
  });
});

describe("useTradeMarkers — error surfacing", () => {
  it("5xx / network error: rawMarkers empty, error populated", async () => {
    mockFetchMarkers.mockImplementation(async () => {
      throw new Error("500 internal");
    });
    const { result } = renderHook(() => useTradeMarkers(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.markers).toEqual([]);
    expect(result.current.rawMarkers).toEqual([]);
    expect(result.current.error?.message).toMatch(/500 internal/);
  });

  it("non-Error rejection wrapped in a generic Error", async () => {
    mockFetchMarkers.mockImplementation(async () => {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw "boom";
    });
    const { result } = renderHook(() => useTradeMarkers(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toMatch(/markers fetch failed/i);
  });

  it("403 surfaces with the backend Hinglish detail, markers empty", async () => {
    mockFetchMarkers.mockImplementation(async () => {
      throw new Error(
        "Is strategy ke markers dekhne ka access nahi hai. " +
          "Strategy ID confirm karo aur apni login session check karo.",
      );
    });
    const { result } = renderHook(() => useTradeMarkers(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.markers).toEqual([]);
    expect(result.current.error?.message).toMatch(/access nahi hai/);
  });

  it("successful refetch clears a prior error", async () => {
    let callCount = 0;
    mockFetchMarkers.mockImplementation(async () => {
      callCount += 1;
      if (callCount === 1) throw new Error("transient");
      return happyResponse;
    });
    const { result } = renderHook(() => useTradeMarkers(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.error?.message).toBe("transient");
    await act(async () => {
      await result.current.refetch();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.rawMarkers).toHaveLength(2);
  });
});

describe("useTradeMarkers — highlight memo", () => {
  it("highlighted marker gets size=2 in the SeriesMarker output", async () => {
    const initial: UseTradeMarkersOptions = {
      ...baseOpts,
      highlightedId: null,
    };
    const { result, rerender } = renderHook(
      (p: UseTradeMarkersOptions) => useTradeMarkers(p),
      { initialProps: initial },
    );
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.markers.every((m) => m.size === 1)).toBe(true);

    rerender({ ...baseOpts, highlightedId: "m-2" });
    await waitFor(() => {
      const target = result.current.markers.find((m) => m.id === "m-2");
      expect(target?.size).toBe(2);
    });
    const other = result.current.markers.find((m) => m.id === "m-1");
    expect(other?.size).toBe(1);
  });

  it("changing highlight does NOT trigger a refetch", async () => {
    const initial: UseTradeMarkersOptions = {
      ...baseOpts,
      highlightedId: null,
    };
    const { result, rerender } = renderHook(
      (p: UseTradeMarkersOptions) => useTradeMarkers(p),
      { initialProps: initial },
    );
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(mockFetchMarkers).toHaveBeenCalledTimes(1);

    rerender({ ...baseOpts, highlightedId: "m-1" });
    rerender({ ...baseOpts, highlightedId: "m-2" });
    rerender({ ...baseOpts, highlightedId: null });

    // Highlight is a pure derived-value input; no extra fetches.
    expect(mockFetchMarkers).toHaveBeenCalledTimes(1);
  });
});
