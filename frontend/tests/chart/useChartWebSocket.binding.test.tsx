/**
 * useChartWebSocket — binding-layer tests.
 *
 * Scope is deliberately tight: verify that the React hook wires the
 * right transport methods on the right prop changes. The transport
 * itself is mocked at module level so this file does NOT re-test the
 * WS state machine (that's ``chart_ws_transport.test.ts``'s job).
 *
 * Why these 4 tests are sufficient:
 *   1. ``mount`` proves the hook constructs a transport, subscribes,
 *      and opens with the initial params + token version.
 *   2. ``unmount`` proves cleanup closes the transport (no leaks).
 *   3. ``tokenVersion change`` proves token refresh routes through
 *      ``updateToken`` on the SAME transport (no React-level
 *      remount).
 *   4. ``sessionExpired change`` proves R1 prop routes through
 *      ``setSessionExpired`` on the SAME transport.
 *
 * Everything else the hook does — reducer dispatch on transport
 * events, seed reset via ref-compare — is plumbing best verified by
 * downstream component tests (A2) or the transport's own tests.
 */

import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";
import { renderHook } from "@testing-library/react";

interface FakeTransport {
  open: Mock;
  close: Mock;
  setSessionExpired: Mock;
  updateToken: Mock;
  subscribe: Mock;
  getReconnectAttempt: Mock;
  isSessionExpired: Mock;
  getTokenVersion: Mock;
  _tokenVersion: number;
}

const transports: FakeTransport[] = [];

function makeFakeTransport(): FakeTransport {
  const t: FakeTransport = {
    _tokenVersion: 0,
    open: vi.fn(),
    close: vi.fn(),
    setSessionExpired: vi.fn(),
    updateToken: vi.fn(),
    subscribe: vi.fn(() => () => {}),
    getReconnectAttempt: vi.fn(() => 0),
    isSessionExpired: vi.fn(() => false),
    getTokenVersion: vi.fn(),
  };
  // The hook's first-render token-effect uses ``getTokenVersion()``
  // to no-op when the transport already has the current version. Our
  // fake tracks the version through ``open`` / ``updateToken`` so
  // that guard works as it would against the real class.
  t.open.mockImplementation((_params: unknown, version: number) => {
    t._tokenVersion = version;
  });
  t.updateToken.mockImplementation((_token: unknown, version: number) => {
    t._tokenVersion = version;
  });
  t.getTokenVersion.mockImplementation(() => t._tokenVersion);
  return t;
}

// NOTE: vi.fn() with an arrow-function impl cannot be used as a
// constructor (arrows lack [[Construct]]). The hook calls
// ``new ChartWsTransport(...)``, so the mock implementation must be
// a regular (non-arrow) function — its returned object replaces the
// ``this`` of the synthetic instance per JS ``new`` semantics.
vi.mock("@/lib/chart/chart_ws_transport", () => ({
  ChartWsTransport: vi.fn(function FakeTransportCtor() {
    const t = makeFakeTransport();
    transports.push(t);
    return t;
  }),
  reconnectDelayMs: vi.fn(),
}));

// Import the hook AFTER vi.mock is hoisted.
// eslint-disable-next-line import/first
import { useChartWebSocket } from "@/hooks/useChartWebSocket";

beforeEach(() => {
  transports.length = 0;
  vi.clearAllMocks();
});

afterEach(() => {
  // Restore is unnecessary because vi.mock is module-scoped and
  // clearAllMocks runs in beforeEach, but be explicit anyway.
  vi.restoreAllMocks();
});

const baseProps = {
  symbol: "NIFTY",
  timeframe: "5m" as const,
  token: "tok-A",
  tokenVersion: 1,
  initialCandles: [],
};

describe("useChartWebSocket — binding to ChartWsTransport", () => {
  it("mount: constructs a transport, subscribes, opens with initial params", () => {
    renderHook(() => useChartWebSocket(baseProps));

    expect(transports).toHaveLength(1);
    const t = transports[0];

    expect(t.subscribe).toHaveBeenCalledTimes(1);
    expect(t.setSessionExpired).toHaveBeenCalledWith(false);
    expect(t.open).toHaveBeenCalledWith(
      { symbol: "NIFTY", timeframe: "5m", token: "tok-A" },
      1,
    );
  });

  it("unmount: calls transport.close()", () => {
    const { unmount } = renderHook(() => useChartWebSocket(baseProps));
    const t = transports[0];

    unmount();

    expect(t.close).toHaveBeenCalledTimes(1);
  });

  it("tokenVersion change: routes through transport.updateToken on the same instance", () => {
    const { rerender } = renderHook(
      (props: { token: string; tokenVersion: number }) =>
        useChartWebSocket({ ...baseProps, ...props }),
      { initialProps: { token: "tok-A", tokenVersion: 1 } },
    );

    const t = transports[0];
    // The mount effect's open(...) already set the version to 1, so
    // the first-render token-effect no-op'd. Sanity check + reset.
    expect(t.updateToken).not.toHaveBeenCalled();

    rerender({ token: "tok-B", tokenVersion: 2 });

    expect(transports).toHaveLength(1); // No new transport (no remount)
    expect(t.updateToken).toHaveBeenCalledTimes(1);
    expect(t.updateToken).toHaveBeenCalledWith("tok-B", 2);
  });

  it("sessionExpired change: routes through transport.setSessionExpired", () => {
    const { rerender } = renderHook(
      (props: { sessionExpired: boolean }) =>
        useChartWebSocket({ ...baseProps, ...props }),
      { initialProps: { sessionExpired: false } },
    );

    const t = transports[0];
    // Mount-time setSessionExpired(false) calls — clear so the
    // post-rerender assertion sees only the prop-change call.
    t.setSessionExpired.mockClear();

    rerender({ sessionExpired: true });

    expect(transports).toHaveLength(1);
    expect(t.setSessionExpired).toHaveBeenCalledWith(true);
  });
});
