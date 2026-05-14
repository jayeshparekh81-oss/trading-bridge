import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { api } from "@/lib/api";
import {
  buildChartWsUrl,
  fetchChartHistory,
  fetchChartMarkers,
  fetchOlderHistory,
  fetchWsToken,
} from "@/lib/chart/api";
import { fetchUserStrategies } from "@/lib/chart/strategies";

const mockedGet = vi.mocked(api.get);

describe("fetchChartHistory", () => {
  beforeEach(() => {
    mockedGet.mockReset();
  });

  it("delegates to api.get with the correct query string", async () => {
    mockedGet.mockResolvedValue({
      symbol: "NIFTY",
      timeframe: "5m",
      from_ts: "a",
      to_ts: "b",
      cached: false,
      candles: [],
    });
    await fetchChartHistory({
      symbol: "NIFTY",
      exchange: "NSE",
      timeframe: "5m",
      from: "2026-01-15T09:15:00+05:30",
      to: "2026-01-15T15:30:00+05:30",
    });
    expect(mockedGet).toHaveBeenCalledTimes(1);
    const url = mockedGet.mock.calls[0][0] as string;
    expect(url.startsWith("/chart/history?")).toBe(true);
    expect(url).toContain("symbol=NIFTY");
    expect(url).toContain("timeframe=5m");
  });

  it("returns mock fixture under forceMock without calling api.get", async () => {
    const resp = await fetchChartHistory({
      symbol: "NIFTY",
      exchange: "NSE",
      timeframe: "5m",
      from: "a",
      to: "b",
      forceMock: true,
    });
    expect(resp.candles).toHaveLength(200);
    expect(mockedGet).not.toHaveBeenCalled();
  });
});

describe("fetchOlderHistory — Phase 5", () => {
  beforeEach(() => mockedGet.mockReset());

  it("returns the synthetic mock fixture when forceMock=true (no api.get)", async () => {
    const resp = await fetchOlderHistory({
      symbol: "NIFTY",
      exchange: "NSE",
      timeframe: "5m",
      beforeEpochSeconds: 1_800_000_000,
      barCount: 50,
      forceMock: true,
    });
    expect(resp.candles).toHaveLength(50);
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it("hits /chart/history with from/to derived from beforeEpochSeconds + barCount", async () => {
    mockedGet.mockResolvedValue({
      symbol: "NIFTY",
      timeframe: "5m",
      from_ts: "a",
      to_ts: "b",
      cached: false,
      candles: [],
    });
    const before = 1_800_000_000;
    await fetchOlderHistory({
      symbol: "NIFTY",
      exchange: "NSE",
      timeframe: "5m",
      beforeEpochSeconds: before,
      barCount: 100,
      forceMock: false,
    });
    expect(mockedGet).toHaveBeenCalledTimes(1);
    const url = mockedGet.mock.calls[0][0] as string;
    expect(url.startsWith("/chart/history?")).toBe(true);
    const tfSeconds = 300;
    const expectedToIso = new Date((before - tfSeconds) * 1_000).toISOString();
    const expectedFromIso = new Date(
      (before - tfSeconds * 100) * 1_000,
    ).toISOString();
    expect(url).toContain(`to=${encodeURIComponent(expectedToIso)}`);
    expect(url).toContain(`from=${encodeURIComponent(expectedFromIso)}`);
  });

  it("defaults barCount to 200", async () => {
    mockedGet.mockResolvedValue({
      symbol: "X",
      timeframe: "5m",
      from_ts: "",
      to_ts: "",
      cached: false,
      candles: [],
    });
    const before = 1_800_000_000;
    await fetchOlderHistory({
      symbol: "X",
      exchange: "NSE",
      timeframe: "5m",
      beforeEpochSeconds: before,
      forceMock: false,
    });
    const url = mockedGet.mock.calls[0][0] as string;
    const tfSeconds = 300;
    const expectedFromIso = new Date(
      (before - tfSeconds * 200) * 1_000,
    ).toISOString();
    expect(url).toContain(`from=${encodeURIComponent(expectedFromIso)}`);
  });
});

describe("fetchChartMarkers — Phase 7", () => {
  beforeEach(() => mockedGet.mockReset());

  it("returns the synthetic mock fixture under forceMock (no api.get)", async () => {
    const resp = await fetchChartMarkers({
      strategyId: "11111111-1111-1111-1111-111111111111",
      symbol: "NIFTY",
      timeframe: "5m",
      fromIso: "2026-05-12T03:45:00.000Z",
      toIso: "2026-05-12T10:00:00.000Z",
      forceMock: true,
    });
    expect(resp.markers.length).toBeGreaterThan(0);
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it("hits /chart/markers with the documented query string", async () => {
    mockedGet.mockResolvedValue({
      strategy_id: "x",
      symbol: "NIFTY",
      timeframe: "5m",
      from_ts: "",
      to_ts: "",
      cached: false,
      markers: [],
    });
    await fetchChartMarkers({
      strategyId: "11111111-1111-1111-1111-111111111111",
      symbol: "NIFTY",
      timeframe: "5m",
      fromIso: "2026-05-12T03:45:00.000Z",
      toIso: "2026-05-12T10:00:00.000Z",
      forceMock: false,
    });
    expect(mockedGet).toHaveBeenCalledTimes(1);
    const url = mockedGet.mock.calls[0][0] as string;
    expect(url.startsWith("/chart/markers?")).toBe(true);
    expect(url).toContain("strategy_id=11111111");
    expect(url).toContain("symbol=NIFTY");
    expect(url).toContain("timeframe=5m");
  });
});

describe("fetchWsToken", () => {
  beforeEach(() => mockedGet.mockReset());

  it("delegates to /chart/ws-token", async () => {
    mockedGet.mockResolvedValue({ token: "abc", expires_in: 900 });
    const out = await fetchWsToken();
    expect(mockedGet).toHaveBeenCalledWith("/chart/ws-token");
    expect(out).toEqual({ token: "abc", expires_in: 900 });
  });

  it("returns placeholder under forceMock", async () => {
    const out = await fetchWsToken({ forceMock: true });
    expect(out.token).toBe("mock-ws-token");
    expect(out.expires_in).toBe(900);
    expect(mockedGet).not.toHaveBeenCalled();
  });
});

describe("fetchUserStrategies — Day 3 / Phase 1", () => {
  beforeEach(() => mockedGet.mockReset());

  it("returns the synthetic mock fixture under forceMock (no api.get)", async () => {
    const resp = await fetchUserStrategies({ forceMock: true });
    expect(resp.strategies.length).toBeGreaterThan(0);
    expect(mockedGet).not.toHaveBeenCalled();
  });

  it("hits /strategies in real mode", async () => {
    mockedGet.mockResolvedValue({ strategies: [], count: 0 });
    await fetchUserStrategies({ forceMock: false });
    expect(mockedGet).toHaveBeenCalledWith("/strategies");
  });
});

describe("buildChartWsUrl", () => {
  const originalApi = process.env.NEXT_PUBLIC_API_URL;
  afterEach(() => {
    process.env.NEXT_PUBLIC_API_URL = originalApi;
  });

  it("swaps http→ws and https→wss", () => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";
    expect(
      buildChartWsUrl({ symbol: "NIFTY", timeframe: "5m", token: "T" }),
    ).toBe("ws://localhost:8000/ws/chart/NIFTY/5m?token=T");
    process.env.NEXT_PUBLIC_API_URL = "https://api.tradetri.com";
    expect(
      buildChartWsUrl({ symbol: "NIFTY", timeframe: "5m", token: "T" }),
    ).toBe("wss://api.tradetri.com/ws/chart/NIFTY/5m?token=T");
  });

  it("URL-encodes symbol and token", () => {
    process.env.NEXT_PUBLIC_API_URL = "https://x.com";
    const url = buildChartWsUrl({
      symbol: "NSE:NIFTY",
      timeframe: "5m",
      token: "abc xyz",
    });
    expect(url).toContain("NSE%3ANIFTY");
    expect(url).toContain("abc%20xyz");
  });

  it("uppercases symbol", () => {
    process.env.NEXT_PUBLIC_API_URL = "https://x.com";
    const url = buildChartWsUrl({
      symbol: "nifty",
      timeframe: "5m",
      token: "t",
    });
    expect(url).toContain("/chart/NIFTY/");
  });

  it("falls back to window.location.origin when API URL is unset", () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    // jsdom sets a default origin we can introspect.
    const expected = window.location.origin
      .replace(/^http/i, "ws");
    const url = buildChartWsUrl({
      symbol: "NIFTY",
      timeframe: "5m",
      token: "T",
    });
    expect(url.startsWith(expected)).toBe(true);
  });
});
