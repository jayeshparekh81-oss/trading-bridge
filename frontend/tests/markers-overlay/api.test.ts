/**
 * URL builder + fetcher tests for the Phase E markers-overlay API
 * wrapper. URL builders are pure → assert the exact querystring.
 * Fetchers are thin shells over ``api.get`` → mock ``@/lib/api`` at
 * the file level and assert dispatch.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockApiGet = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    get: (...args: unknown[]) => mockApiGet(...args),
  },
}));

// eslint-disable-next-line import/first
import { buildMarkersUrl, fetchMarkers } from "@/lib/markers-overlay/api";

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiGet.mockResolvedValue({});
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("buildMarkersUrl", () => {
  it("emits strategy_id + mode as the minimum querystring", () => {
    const url = buildMarkersUrl({ strategyId: "abc", mode: "PAPER" });
    expect(url).toBe("/markers?strategy_id=abc&mode=PAPER");
  });

  it("appends from + to when provided", () => {
    const url = buildMarkersUrl({
      strategyId: "abc",
      mode: "BACKTEST",
      fromIso: "2026-05-01T00:00:00+00:00",
      toIso: "2026-05-14T00:00:00+00:00",
    });
    expect(url).toContain("strategy_id=abc");
    expect(url).toContain("mode=BACKTEST");
    expect(url).toContain("from=2026-05-01T00%3A00%3A00%2B00%3A00");
    expect(url).toContain("to=2026-05-14T00%3A00%3A00%2B00%3A00");
  });

  it("appends symbol + side when provided", () => {
    const url = buildMarkersUrl({
      strategyId: "abc",
      mode: "LIVE",
      symbol: "NIFTY",
      side: "LONG_ENTRY",
    });
    expect(url).toContain("symbol=NIFTY");
    expect(url).toContain("side=LONG_ENTRY");
  });

  it("appends limit + offset when provided", () => {
    const url = buildMarkersUrl({
      strategyId: "abc",
      mode: "PAPER",
      limit: 250,
      offset: 100,
    });
    expect(url).toContain("limit=250");
    expect(url).toContain("offset=100");
  });

  it("does NOT append from/to when null", () => {
    const url = buildMarkersUrl({
      strategyId: "abc",
      mode: "PAPER",
      fromIso: null,
      toIso: null,
    });
    expect(url).not.toContain("from=");
    expect(url).not.toContain("to=");
  });

  it("does NOT append symbol/side when null", () => {
    const url = buildMarkersUrl({
      strategyId: "abc",
      mode: "PAPER",
      symbol: null,
      side: null,
    });
    expect(url).not.toContain("symbol=");
    expect(url).not.toContain("side=");
  });

  it("does NOT append limit/offset when null", () => {
    const url = buildMarkersUrl({
      strategyId: "abc",
      mode: "PAPER",
      limit: null,
      offset: null,
    });
    expect(url).not.toContain("limit=");
    expect(url).not.toContain("offset=");
  });

  it("explicit 0 offset still appends (zero is a valid offset)", () => {
    const url = buildMarkersUrl({
      strategyId: "abc",
      mode: "PAPER",
      offset: 0,
    });
    expect(url).toContain("offset=0");
  });

  it("preserves uuid-shaped strategy_id verbatim", () => {
    const uuid = "11111111-1111-1111-1111-111111111111";
    const url = buildMarkersUrl({ strategyId: uuid, mode: "PAPER" });
    expect(url).toContain(`strategy_id=${uuid}`);
  });

  it("emits all params together in one querystring", () => {
    const url = buildMarkersUrl({
      strategyId: "abc",
      mode: "BACKTEST",
      fromIso: "2026-05-01T00:00:00+00:00",
      toIso: "2026-05-14T00:00:00+00:00",
      symbol: "RELIANCE",
      side: "SHORT_EXIT",
      limit: 50,
      offset: 25,
    });
    expect(url.startsWith("/markers?")).toBe(true);
    expect(url).toContain("strategy_id=abc");
    expect(url).toContain("mode=BACKTEST");
    expect(url).toContain("symbol=RELIANCE");
    expect(url).toContain("side=SHORT_EXIT");
    expect(url).toContain("limit=50");
    expect(url).toContain("offset=25");
  });
});

describe("fetchMarkers", () => {
  it("dispatches GET via api.get with the built URL", async () => {
    await fetchMarkers({ strategyId: "abc", mode: "PAPER" });
    expect(mockApiGet).toHaveBeenCalledTimes(1);
    expect(mockApiGet).toHaveBeenCalledWith("/markers?strategy_id=abc&mode=PAPER");
  });

  it("returns whatever api.get resolves with (passthrough)", async () => {
    const fixture = {
      strategy_id: "abc",
      mode: "PAPER",
      limit: 100,
      offset: 0,
      total: 0,
      markers: [],
    };
    mockApiGet.mockResolvedValueOnce(fixture);
    const result = await fetchMarkers({ strategyId: "abc", mode: "PAPER" });
    expect(result).toBe(fixture);
  });

  it("propagates rejections from api.get", async () => {
    mockApiGet.mockRejectedValueOnce(new Error("network down"));
    await expect(
      fetchMarkers({ strategyId: "abc", mode: "PAPER" }),
    ).rejects.toThrow("network down");
  });
});
