/**
 * API-wrapper tests — URL builders + fetcher dispatch.
 *
 * URL builders are pure → assert the exact querystring without
 * mocking. Fetchers are thin shells over ``api.get`` → mock
 * ``@/lib/api`` at the file level and assert the path passed in.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockApiGet = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    get: (...args: unknown[]) => mockApiGet(...args),
  },
}));

// eslint-disable-next-line import/first
import {
  buildEquityUrl,
  buildMetricsUrl,
  buildTradesUrl,
  fetchStrategyTesterEquity,
  fetchStrategyTesterMetrics,
  fetchStrategyTesterTrades,
} from "@/lib/strategy-tester/api";

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiGet.mockResolvedValue({});
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("buildMetricsUrl", () => {
  it("requires mode; omits window + starting_equity when not provided", () => {
    const url = buildMetricsUrl({ strategyId: "abc", mode: "PAPER" });
    expect(url).toBe("/strategy-tester/abc/metrics?mode=PAPER");
  });

  it("appends from + to + starting_equity when provided", () => {
    const url = buildMetricsUrl({
      strategyId: "abc",
      mode: "BACKTEST",
      fromIso: "2026-05-01T00:00:00+00:00",
      toIso: "2026-05-14T00:00:00+00:00",
      startingEquity: 50000,
    });
    expect(url).toContain("mode=BACKTEST");
    expect(url).toContain("from=2026-05-01T00%3A00%3A00%2B00%3A00");
    expect(url).toContain("to=2026-05-14T00%3A00%3A00%2B00%3A00");
    expect(url).toContain("starting_equity=50000");
  });

  it("does NOT append starting_equity when explicitly null", () => {
    const url = buildMetricsUrl({
      strategyId: "abc",
      mode: "LIVE",
      startingEquity: null,
    });
    expect(url).not.toContain("starting_equity");
  });
});

describe("buildEquityUrl", () => {
  it("includes mode + starting_equity + window when provided", () => {
    const url = buildEquityUrl({
      strategyId: "s1",
      mode: "PAPER",
      startingEquity: 100000,
      fromIso: "2026-05-01T00:00:00+00:00",
      toIso: "2026-05-14T00:00:00+00:00",
    });
    expect(url).toContain("/strategy-tester/s1/equity?");
    expect(url).toContain("mode=PAPER");
    expect(url).toContain("starting_equity=100000");
    expect(url).toContain("from=");
    expect(url).toContain("to=");
  });
});

describe("buildTradesUrl", () => {
  it("appends symbol + limit + offset when provided", () => {
    const url = buildTradesUrl({
      strategyId: "s1",
      mode: "PAPER",
      symbol: "RELIANCE",
      limit: 50,
      offset: 100,
    });
    expect(url).toContain("symbol=RELIANCE");
    expect(url).toContain("limit=50");
    expect(url).toContain("offset=100");
  });

  it("omits optional params when null", () => {
    const url = buildTradesUrl({
      strategyId: "s1",
      mode: "PAPER",
      symbol: null,
      limit: null,
      offset: null,
    });
    expect(url).not.toContain("symbol");
    expect(url).not.toContain("limit");
    expect(url).not.toContain("offset");
  });
});

describe("fetchStrategyTesterMetrics", () => {
  it("dispatches api.get with the built URL", async () => {
    await fetchStrategyTesterMetrics({ strategyId: "abc", mode: "PAPER" });
    expect(mockApiGet).toHaveBeenCalledTimes(1);
    expect(mockApiGet).toHaveBeenCalledWith(
      "/strategy-tester/abc/metrics?mode=PAPER",
    );
  });
});

describe("fetchStrategyTesterEquity", () => {
  it("dispatches api.get with the built URL", async () => {
    await fetchStrategyTesterEquity({ strategyId: "abc", mode: "BACKTEST" });
    expect(mockApiGet).toHaveBeenCalledTimes(1);
    const [path] = mockApiGet.mock.calls[0];
    expect(path).toContain("/strategy-tester/abc/equity");
    expect(path).toContain("mode=BACKTEST");
  });
});

describe("fetchStrategyTesterTrades", () => {
  it("dispatches api.get with the built URL", async () => {
    await fetchStrategyTesterTrades({
      strategyId: "abc",
      mode: "LIVE",
      limit: 10,
    });
    expect(mockApiGet).toHaveBeenCalledTimes(1);
    const [path] = mockApiGet.mock.calls[0];
    expect(path).toContain("/strategy-tester/abc/trades");
    expect(path).toContain("mode=LIVE");
    expect(path).toContain("limit=10");
  });
});
