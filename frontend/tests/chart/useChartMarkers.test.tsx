/**
 * useChartMarkers — Phase 7 hook tests.
 *
 * Two layers:
 *   1. Mock-mode happy path (forceMock=true) — exercises the real
 *      hook against the synthetic ``getMockMarkers`` fixture.
 *   2. Failure-path tests — mock ``@/lib/chart/api`` at the file
 *      level and rebind the mocked fn per test. Avoids the
 *      ``vi.doMock`` + dynamic-import + ``vi.resetModules()`` dance,
 *      which clobbers React's module cache and surfaces as
 *      ``result.current === null`` inside renderHook.
 */

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockFetchChartMarkers = vi.fn();

vi.mock("@/lib/chart/api", () => ({
  fetchChartMarkers: (...args: unknown[]) => mockFetchChartMarkers(...args),
}));

// eslint-disable-next-line import/first
import { useChartMarkers } from "@/hooks/useChartMarkers";

const baseOpts = {
  strategyId: "11111111-1111-1111-1111-111111111111",
  symbol: "NIFTY",
  timeframe: "5m" as const,
  fromIso: "2026-05-12T03:45:00.000Z",
  toIso: "2026-05-12T10:00:00.000Z",
};

const happyResponse = {
  strategy_id: baseOpts.strategyId,
  symbol: "NIFTY",
  timeframe: "5m",
  from_ts: baseOpts.fromIso,
  to_ts: baseOpts.toIso,
  cached: false,
  markers: [
    {
      kind: "ENTRY" as const,
      timestamp: "2026-05-12T05:00:00.000Z",
      price: "22500.00",
      quantity: 50,
      side: "BUY",
      pnl: null,
      exit_reason: null,
    },
    {
      kind: "TP_HIT" as const,
      timestamp: "2026-05-12T06:00:00.000Z",
      price: "22600.00",
      quantity: 50,
      side: "BUY",
      pnl: "5000.00",
      exit_reason: "target",
    },
  ],
};

beforeEach(() => {
  vi.useRealTimers();
  mockFetchChartMarkers.mockReset();
  // Default the mocked fetch to the happy response so happy-path
  // tests don't need to repeat the wiring.
  mockFetchChartMarkers.mockResolvedValue(happyResponse);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useChartMarkers — disabled paths", () => {
  it("starts empty + idle when fully-disabled (null strategyId)", () => {
    const { result } = renderHook(() =>
      useChartMarkers({ ...baseOpts, strategyId: null }),
    );
    expect(result.current.markers).toEqual([]);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.hasLoaded).toBe(false);
    expect(result.current.error).toBeNull();
    expect(mockFetchChartMarkers).not.toHaveBeenCalled();
  });

  it("does NOT fetch while ``enabled=false`` even when all inputs are non-null", () => {
    const { result } = renderHook(() =>
      useChartMarkers({ ...baseOpts, enabled: false }),
    );
    expect(result.current.isLoading).toBe(false);
    expect(result.current.markers).toEqual([]);
    expect(mockFetchChartMarkers).not.toHaveBeenCalled();
  });

  it("does NOT fetch while ``fromIso`` is null (waiting on candles)", () => {
    const { result } = renderHook(() =>
      useChartMarkers({ ...baseOpts, fromIso: null }),
    );
    expect(result.current.isLoading).toBe(false);
    expect(mockFetchChartMarkers).not.toHaveBeenCalled();
  });

  it("does NOT fetch while ``toIso`` is null (waiting on candles)", () => {
    const { result } = renderHook(() =>
      useChartMarkers({ ...baseOpts, toIso: null }),
    );
    expect(result.current.isLoading).toBe(false);
    expect(mockFetchChartMarkers).not.toHaveBeenCalled();
  });

  it("refetch() called while disabled is a synchronous no-op (early return path)", async () => {
    const { result } = renderHook(() =>
      useChartMarkers({ ...baseOpts, enabled: false }),
    );
    expect(mockFetchChartMarkers).not.toHaveBeenCalled();
    // Manual refetch call while disabled — must not fire fetch and
    // must not enter loading state.
    await act(async () => {
      await result.current.refetch();
    });
    expect(mockFetchChartMarkers).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });
});

describe("useChartMarkers — happy path", () => {
  it("fetches + populates markers in render-ready numeric form", async () => {
    const { result } = renderHook(() => useChartMarkers(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.markers).toHaveLength(2);
    // Numeric form — price is a number, time is epoch seconds.
    for (const m of result.current.markers) {
      expect(typeof m.price).toBe("number");
      expect(typeof m.time).toBe("number");
    }
    expect(mockFetchChartMarkers).toHaveBeenCalledTimes(1);
  });

  it("forwards the documented options to fetchChartMarkers", async () => {
    const { result } = renderHook(() =>
      useChartMarkers({ ...baseOpts, forceMock: true }),
    );
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    const [arg] = mockFetchChartMarkers.mock.calls[0];
    expect(arg).toMatchObject({
      strategyId: baseOpts.strategyId,
      symbol: "NIFTY",
      timeframe: "5m",
      fromIso: baseOpts.fromIso,
      toIso: baseOpts.toIso,
      forceMock: true,
    });
  });

  it("re-fetches on strategyId change", async () => {
    const { result, rerender } = renderHook(
      (props: typeof baseOpts) => useChartMarkers(props),
      { initialProps: baseOpts },
    );
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(mockFetchChartMarkers).toHaveBeenCalledTimes(1);

    rerender({
      ...baseOpts,
      strategyId: "22222222-2222-2222-2222-222222222222",
    });
    await waitFor(() => expect(mockFetchChartMarkers).toHaveBeenCalledTimes(2));
  });

  it("refetch() callback re-runs the fetch on demand", async () => {
    const { result, unmount } = renderHook(() => useChartMarkers(baseOpts));
    await waitFor(() => expect(result.current.hasLoaded).toBe(true));
    expect(mockFetchChartMarkers).toHaveBeenCalledTimes(1);

    await act(async () => {
      await result.current.refetch();
    });
    expect(mockFetchChartMarkers).toHaveBeenCalledTimes(2);
    expect(result.current.error).toBeNull();
    // Explicit unmount so the next test starts with a clean React tree —
    // pending in-flight promises from this test don't bleed across.
    unmount();
  });
});

describe("useChartMarkers — failure path", () => {
  // Use ``mockImplementation(() => Promise.reject(...))`` rather than
  // ``mockRejectedValue(...)``. The latter eagerly constructs the
  // rejected promise at the moment the mock is configured — vitest
  // can flag that as an unhandled rejection before the hook's
  // try/catch ever sees it, causing waitFor to time out.

  it("surfaces fetch errors via ``error`` state", async () => {
    mockFetchChartMarkers.mockImplementation(async () => {
      throw new Error("strategy not found");
    });
    const { result } = renderHook(() => useChartMarkers(baseOpts));
    // Direct microtask drain — waitFor seems to have a stale-closure
    // issue against the fast error transition; a single tick is
    // enough since the rejection resolves on the next microtask.
    await new Promise((r) => setTimeout(r, 30));
    expect(result.current.hasLoaded).toBe(true);
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toMatch(/strategy not found/i);
    expect(result.current.markers).toEqual([]);
  });

  it("non-Error thrown values are wrapped in a generic Error", async () => {
    mockFetchChartMarkers.mockImplementation(async () => {
      // eslint-disable-next-line @typescript-eslint/only-throw-error
      throw "plain string";
    });
    const { result } = renderHook(() => useChartMarkers(baseOpts));
    await new Promise((r) => setTimeout(r, 30));
    expect(result.current.hasLoaded).toBe(true);
    expect(result.current.error?.message).toMatch(/markers fetch failed/i);
  });

  it("a successful refetch clears a prior error", async () => {
    let callCount = 0;
    mockFetchChartMarkers.mockImplementation(async () => {
      callCount += 1;
      if (callCount === 1) throw new Error("transient");
      return happyResponse;
    });
    const { result } = renderHook(() => useChartMarkers(baseOpts));
    await new Promise((r) => setTimeout(r, 30));
    expect(result.current.error?.message).toBe("transient");

    // Await the refetch promise inside act() so React flushes the
    // post-resolution setState before we assert.
    await act(async () => {
      await result.current.refetch();
    });
    expect(result.current.error).toBeNull();
    expect(result.current.markers).toHaveLength(2);
  });
});
