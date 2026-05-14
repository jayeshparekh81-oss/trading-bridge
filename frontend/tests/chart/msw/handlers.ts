/**
 * MSW handlers + WS server for chart-module tests.
 *
 * Two surfaces:
 *
 *   1. **REST handlers** — intercept the chart REST endpoints so the
 *      WS hook can be tested in isolation without standing up the
 *      whole `useWsToken` / `useChartHistory` pipeline. Tests that
 *      DO want to exercise the full pipeline will override these via
 *      ``server.use(...)`` per-test.
 *
 *   2. **WS link** — msw 2.x's ``ws.link()`` intercepts every
 *      WebSocket constructor that matches the URL pattern. The
 *      returned ``link`` exposes an ``addEventListener("connection",
 *      ...)`` handler where we drive the per-test fake server.
 *      The wildcard ``:symbol/:timeframe`` path means a single
 *      handler covers all (symbol, timeframe) combinations.
 *
 * Per-test usage pattern:
 *
 *   import { server, openChartWs, sendCandle, sendDisconnect } from
 *     "./msw/handlers";
 *
 *   const ws = openChartWs();
 *   await ws.opened;
 *   sendCandle(ws, { ... });
 *   sendDisconnect(ws, { reason: "TimeoutError" });
 *
 * The helpers are deliberately thin — they encapsulate the msw API
 * surface so individual tests stay readable.
 */

import { HttpResponse, http, ws } from "msw";
import { setupServer } from "msw/node";

import type {
  BrokerDisconnectedEnvelope,
  BrokerReconnectedEnvelope,
  CandleEnvelope,
  HeartbeatEnvelope,
  WireCandle,
  WsTokenResponse,
} from "@/lib/chart/types";

// ─────────────────────────────────────────────────────────────────────
// REST handlers (overridable per-test via server.use(...))
// ─────────────────────────────────────────────────────────────────────

const DEFAULT_BASE = "http://localhost:8000";

const defaultTokenResponse: WsTokenResponse = {
  token: "test-token-default",
  expires_in: 900,
};

export const restHandlers = [
  http.get(`${DEFAULT_BASE}/api/chart/ws-token`, () =>
    HttpResponse.json(defaultTokenResponse),
  ),
  http.get(`${DEFAULT_BASE}/api/chart/history`, () =>
    HttpResponse.json({
      symbol: "NIFTY",
      timeframe: "5m",
      from_ts: new Date(Date.now() - 1_000_000).toISOString(),
      to_ts: new Date().toISOString(),
      cached: false,
      candles: [] as WireCandle[],
    }),
  ),
];

// ─────────────────────────────────────────────────────────────────────
// WS link — wildcard symbol + timeframe + token query
// ─────────────────────────────────────────────────────────────────────

const chartWs = ws.link(`${DEFAULT_BASE.replace(/^http/, "ws")}/ws/chart/*`);

/**
 * Per-test connection registry. The `connection` event fires inside
 * msw's worker for each new WebSocket the SUT opens. We push the
 * client handle into ``activeConnections`` so individual tests can
 * drive them via the ``send*`` helpers below.
 *
 * Reset between tests via the autouse ``afterEach`` in ``tests/setup.ts``.
 */
interface ActiveConn {
  url: string;
  client: { send: (msg: string) => void; close: () => void };
  /** Resolved when the underlying browser-side WS finishes ``onopen``. */
  opened: Promise<void>;
}

export const activeConnections: ActiveConn[] = [];

const wsHandler = chartWs.addEventListener("connection", ({ client }) => {
  let resolveOpened!: () => void;
  const opened = new Promise<void>((r) => {
    resolveOpened = r;
  });
  // The browser-side ``WebSocket.onopen`` fires once msw routes the
  // virtual connection. We resolve immediately because msw sets the
  // readyState synchronously for the consumer.
  resolveOpened();

  activeConnections.push({
    url: client.url.toString(),
    client: {
      send: (msg: string) => client.send(msg),
      close: () => client.close(),
    },
    opened,
  });
});

// ─────────────────────────────────────────────────────────────────────
// Send helpers — typed per envelope
// ─────────────────────────────────────────────────────────────────────

export function sendCandle(conn: ActiveConn, candle: WireCandle): void {
  const env: CandleEnvelope = { event: "candle", data: candle };
  conn.client.send(JSON.stringify(env));
}

export function sendDisconnect(
  conn: ActiveConn,
  opts: { symbol: string; reason: string; failed_attempts?: number; since?: string },
): void {
  const env: BrokerDisconnectedEnvelope = {
    event: "broker_disconnected",
    symbol: opts.symbol,
    reason: opts.reason,
    failed_attempts: opts.failed_attempts ?? 5,
    since: opts.since ?? new Date().toISOString(),
  };
  conn.client.send(JSON.stringify(env));
}

export function sendReconnect(conn: ActiveConn, symbol: string): void {
  const env: BrokerReconnectedEnvelope = {
    event: "broker_reconnected",
    symbol,
    at: new Date().toISOString(),
  };
  conn.client.send(JSON.stringify(env));
}

export function sendHeartbeat(conn: ActiveConn): void {
  const env: HeartbeatEnvelope = {
    event: "heartbeat",
    at: new Date().toISOString(),
  };
  conn.client.send(JSON.stringify(env));
}

export function sendRaw(conn: ActiveConn, raw: string): void {
  conn.client.send(raw);
}

// ─────────────────────────────────────────────────────────────────────
// Server export
// ─────────────────────────────────────────────────────────────────────

export const server = setupServer(...restHandlers, wsHandler);

export function resetConnections(): void {
  activeConnections.length = 0;
}
