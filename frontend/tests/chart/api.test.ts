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
  fetchWsToken,
} from "@/lib/chart/api";

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
