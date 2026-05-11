import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/chart/api", () => ({
  fetchWsToken: vi.fn(),
}));

import { fetchWsToken } from "@/lib/chart/api";
import { useWsToken } from "@/hooks/useWsToken";

const mockedFetch = vi.mocked(fetchWsToken);

describe("useWsToken", () => {
  beforeEach(() => {
    mockedFetch.mockReset();
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches token on mount and exposes it", async () => {
    mockedFetch.mockResolvedValue({ token: "tok1", expires_in: 900 });
    const { result } = renderHook(() => useWsToken());
    expect(result.current.isLoading).toBe(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.token).toBe("tok1");
    expect(result.current.version).toBe(1);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("refreshes token every 12 minutes", async () => {
    mockedFetch
      .mockResolvedValueOnce({ token: "tok1", expires_in: 900 })
      .mockResolvedValueOnce({ token: "tok2", expires_in: 900 });
    const { result } = renderHook(() => useWsToken());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.token).toBe("tok1");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(12 * 60 * 1000);
    });
    expect(result.current.token).toBe("tok2");
    expect(result.current.version).toBe(2);
  });

  it("captures error and continues loading=false", async () => {
    mockedFetch.mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useWsToken());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.error?.message).toBe("boom");
    expect(result.current.token).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it("enabled=false short-circuits the fetch + loading flag", async () => {
    const { result } = renderHook(() => useWsToken({ enabled: false }));
    // The effect runs synchronously on mount; ``isLoading`` is
    // already false by the first render commit. No async wait
    // needed (and ``waitFor`` would hang under fake timers).
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.isLoading).toBe(false);
    expect(mockedFetch).not.toHaveBeenCalled();
    expect(result.current.token).toBeNull();
  });

  it("clears interval on unmount", async () => {
    mockedFetch.mockResolvedValue({ token: "tok1", expires_in: 900 });
    const { unmount } = renderHook(() => useWsToken());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(mockedFetch).toHaveBeenCalledTimes(1);
    unmount();
    // After unmount, advancing time should NOT trigger another fetch.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(12 * 60 * 1000);
    });
    expect(mockedFetch).toHaveBeenCalledTimes(1);
  });

  it("wraps non-Error throwables into Error instances", async () => {
    mockedFetch.mockRejectedValue("plain string failure");
    const { result } = renderHook(() => useWsToken());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toBe("ws-token fetch failed");
  });
});
