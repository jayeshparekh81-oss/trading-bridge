/**
 * ChartWsTransport — vanilla-JS class owning the chart WebSocket
 * lifecycle. Built for testability: every external dependency
 * (WebSocket constructor, timer scheduler, randomness, mock toggle)
 * is injectable, so unit tests run without React, jsdom, or
 * ``renderHook``.
 *
 * The React hook ``useChartWebSocket`` is a thin wrapper around this
 * class — it creates one transport per (symbol, timeframe), subscribes
 * to its events, and translates them into reducer dispatches. The
 * complex state-machine logic (reconnect, heartbeat, sessionExpired
 * guard, token-refresh path, mock vs real, close-code routing) lives
 * here.
 *
 * Public surface (test-friendly):
 *   - ``open(params, tokenVersion)`` — start the lifecycle
 *   - ``close()`` — idempotent teardown
 *   - ``updateToken(token, version)`` — token-refresh path (R3): close
 *     current socket + reopen with the new token. Reconnect attempts
 *     reset to 0 because a fresh token implies the prior failures
 *     were probably auth-related.
 *   - ``setSessionExpired(value)`` — R1 guard. When ``true``, the
 *     transport stops all reconnect scheduling. The only path back
 *     to live is a fresh ``open()`` after the user re-auths.
 *   - ``subscribe(handler)`` — register a state/candle event listener.
 *     Returns an unsubscribe function.
 *   - Readers: ``getReconnectAttempt()``, ``isSessionExpired()``,
 *     ``getTokenVersion()`` — used by tests + telemetry.
 *
 * Event shape:
 *   - ``{ kind: "status", status }`` — current connection status
 *   - ``{ kind: "candle", candle }`` — parsed candle from a frame
 */

import { buildChartWsUrl } from "./api";
import { createMockWsServer, isMockEnabled } from "./mock_data";
import {
  isBrokerDisconnectedEnvelope,
  isBrokerReconnectedEnvelope,
  isCandleEnvelope,
  parseCandle,
  type Candle,
  type ChartEnvelope,
  type ConnectionStatus,
  type Timeframe,
} from "./types";

// ═══════════════════════════════════════════════════════════════════════
// Tuning constants (mirror backend)
// ═══════════════════════════════════════════════════════════════════════

const RECONNECT_BASE_DELAY_MS = 1_000;
const RECONNECT_MAX_DELAY_MS = 60_000;
const RECONNECT_JITTER_FACTOR = 0.25;
const HEARTBEAT_INTERVAL_MS = 20_000;
const NO_RECONNECT_CODES = new Set([4400, 4401]);

// ═══════════════════════════════════════════════════════════════════════
// Backoff (pure, exported)
// ═══════════════════════════════════════════════════════════════════════

export function reconnectDelayMs(
  attempt: number,
  random: () => number = Math.random,
): number {
  if (attempt <= 0) return 0;
  const base = Math.min(
    RECONNECT_BASE_DELAY_MS * Math.pow(2, attempt - 1),
    RECONNECT_MAX_DELAY_MS,
  );
  const jitter = (random() * 2 - 1) * base * RECONNECT_JITTER_FACTOR;
  return Math.max(0, base + jitter);
}

// ═══════════════════════════════════════════════════════════════════════
// Injection contracts
// ═══════════════════════════════════════════════════════════════════════

export type WebSocketFactory = (url: string) => WebSocket;

export interface TimerScheduler {
  setTimeout: (handler: () => void, ms: number) => unknown;
  clearTimeout: (id: unknown) => void;
  setInterval: (handler: () => void, ms: number) => unknown;
  clearInterval: (id: unknown) => void;
}

const defaultScheduler: TimerScheduler = {
  setTimeout: (h, ms) => setTimeout(h, ms),
  clearTimeout: (id) => clearTimeout(id as ReturnType<typeof setTimeout>),
  setInterval: (h, ms) => setInterval(h, ms),
  clearInterval: (id) => clearInterval(id as ReturnType<typeof setInterval>),
};

const defaultWebSocketFactory: WebSocketFactory = (url) => new WebSocket(url);

// ═══════════════════════════════════════════════════════════════════════
// Public types
// ═══════════════════════════════════════════════════════════════════════

export interface ChartWsTransportOptions {
  webSocketFactory?: WebSocketFactory;
  scheduler?: TimerScheduler;
  /** Forces the mock-emitter path. ``undefined`` means read
   *  ``isMockEnabled()`` from the env. */
  useMock?: boolean;
  /** Randomness source for jitter. Defaults to ``Math.random``. */
  random?: () => number;
}

export interface ChartWsConnectionParams {
  symbol: string;
  timeframe: Timeframe;
  token: string | null;
}

export type ChartWsEvent =
  | { kind: "status"; status: ConnectionStatus }
  | { kind: "candle"; candle: Candle };

export type ChartWsSubscriber = (event: ChartWsEvent) => void;

// ═══════════════════════════════════════════════════════════════════════
// Transport class
// ═══════════════════════════════════════════════════════════════════════

export class ChartWsTransport {
  private socket: WebSocket | null = null;
  private mockServer: ReturnType<typeof createMockWsServer> | null = null;
  private reconnectAttempt = 0;
  private reconnectTimerId: unknown = null;
  private heartbeatTimerId: unknown = null;
  private isDisposed = false;
  private sessionExpired = false;
  private tokenVersion = 0;
  private currentParams: ChartWsConnectionParams | null = null;
  private readonly subscribers = new Set<ChartWsSubscriber>();

  private readonly wsFactory: WebSocketFactory;
  private readonly scheduler: TimerScheduler;
  private readonly useMock: boolean;
  private readonly random: () => number;

  constructor(opts: ChartWsTransportOptions = {}) {
    this.wsFactory = opts.webSocketFactory ?? defaultWebSocketFactory;
    this.scheduler = opts.scheduler ?? defaultScheduler;
    this.useMock = opts.useMock ?? isMockEnabled();
    this.random = opts.random ?? Math.random;
  }

  // ── Lifecycle ──────────────────────────────────────────────────────

  open(params: ChartWsConnectionParams, tokenVersion: number): void {
    if (this.isDisposed) return;
    this.currentParams = params;
    this.tokenVersion = tokenVersion;
    this.connect();
  }

  /** Idempotent teardown. After ``close()`` the transport will not
   *  reopen automatically; the consumer must construct a fresh one. */
  close(): void {
    this.isDisposed = true;
    this.closeExisting();
  }

  /** R1: stale-token guard. ``true`` halts all reconnect scheduling
   *  AND blocks any future ``connect()`` call. */
  setSessionExpired(value: boolean): void {
    this.sessionExpired = value;
    if (value) {
      this.clearTimers();
    }
  }

  /** R3: token-refresh path. Closes the current socket + reopens with
   *  the new token. Resets ``reconnectAttempt`` to 0 because a fresh
   *  token usually means prior failures were auth-related. */
  updateToken(token: string | null, version: number): void {
    if (this.isDisposed || !this.currentParams) return;
    this.currentParams = { ...this.currentParams, token };
    this.tokenVersion = version;
    this.reconnectAttempt = 0;
    this.closeExisting();
    this.connect();
  }

  // ── Observer ───────────────────────────────────────────────────────

  subscribe(handler: ChartWsSubscriber): () => void {
    this.subscribers.add(handler);
    return () => {
      this.subscribers.delete(handler);
    };
  }

  // ── Readers ────────────────────────────────────────────────────────

  getReconnectAttempt(): number {
    return this.reconnectAttempt;
  }

  isSessionExpired(): boolean {
    return this.sessionExpired;
  }

  getTokenVersion(): number {
    return this.tokenVersion;
  }

  // ── Internals ──────────────────────────────────────────────────────

  private emit(event: ChartWsEvent): void {
    for (const sub of this.subscribers) {
      try {
        sub(event);
      } catch {
        // Subscriber errors must not break the transport.
      }
    }
  }

  private clearTimers(): void {
    if (this.reconnectTimerId !== null) {
      this.scheduler.clearTimeout(this.reconnectTimerId);
      this.reconnectTimerId = null;
    }
    if (this.heartbeatTimerId !== null) {
      this.scheduler.clearInterval(this.heartbeatTimerId);
      this.heartbeatTimerId = null;
    }
  }

  private closeExisting(): void {
    this.clearTimers();
    if (this.socket) {
      // Avoid the close-handler triggering another reconnect.
      this.socket.onclose = null;
      this.socket.onerror = null;
      try {
        this.socket.close();
      } catch {
        /* close-time errors must not propagate */
      }
      this.socket = null;
    }
    if (this.mockServer) {
      this.mockServer.stop();
      this.mockServer = null;
    }
  }

  private handleEnvelope(env: ChartEnvelope): void {
    if (this.isDisposed) return;
    if (isCandleEnvelope(env)) {
      try {
        this.emit({ kind: "candle", candle: parseCandle(env.data) });
      } catch {
        // Malformed wire candle — drop the frame.
      }
      return;
    }
    if (isBrokerDisconnectedEnvelope(env)) {
      this.emit({
        kind: "status",
        status: {
          kind: "disconnected",
          reason: env.reason,
          since: env.since,
          failed_attempts: env.failed_attempts,
        },
      });
      return;
    }
    if (isBrokerReconnectedEnvelope(env)) {
      this.emit({ kind: "status", status: { kind: "open" } });
      return;
    }
    // heartbeat → no-op.
  }

  private startHeartbeat(ws: WebSocket): void {
    this.heartbeatTimerId = this.scheduler.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send("ping");
        } catch {
          /* send-on-closing edge — handled by onclose */
        }
      }
    }, HEARTBEAT_INTERVAL_MS);
  }

  private scheduleReconnect(): void {
    if (this.isDisposed) return;
    if (this.sessionExpired) return; // R1
    const attempt = ++this.reconnectAttempt;
    const delay = reconnectDelayMs(attempt, this.random);
    this.reconnectTimerId = this.scheduler.setTimeout(() => {
      this.reconnectTimerId = null;
      this.connect();
    }, delay);
  }

  private connect(): void {
    if (this.isDisposed) return;
    if (this.sessionExpired) return; // R1
    if (!this.currentParams || !this.currentParams.token) return;

    // R2 idempotency: skip if a socket is already alive.
    if (
      this.socket &&
      (this.socket.readyState === WebSocket.CONNECTING ||
        this.socket.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    this.emit({ kind: "status", status: { kind: "connecting" } });

    const { symbol, timeframe, token } = this.currentParams;

    if (this.useMock) {
      const server = createMockWsServer({ symbol, timeframe });
      server.onMessage((env) => this.handleEnvelope(env));
      server.start();
      this.mockServer = server;
      this.reconnectAttempt = 0;
      this.emit({ kind: "status", status: { kind: "open" } });
      return;
    }

    const url = buildChartWsUrl({ symbol, timeframe, token: token ?? "" });
    let ws: WebSocket;
    try {
      ws = this.wsFactory(url);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.socket = ws;

    ws.onopen = () => {
      if (this.isDisposed) {
        try {
          ws.close();
        } catch {
          /* idem */
        }
        return;
      }
      this.reconnectAttempt = 0;
      this.emit({ kind: "status", status: { kind: "open" } });
      this.startHeartbeat(ws);
    };

    ws.onmessage = (event) => {
      if (this.isDisposed) return;
      try {
        const env = JSON.parse(event.data) as ChartEnvelope;
        this.handleEnvelope(env);
      } catch {
        // Non-JSON payload — drop.
      }
    };

    ws.onerror = () => {
      // ``onclose`` fires right after; reconnect scheduled there.
    };

    ws.onclose = (event) => {
      if (this.isDisposed) return;
      if (this.heartbeatTimerId !== null) {
        this.scheduler.clearInterval(this.heartbeatTimerId);
        this.heartbeatTimerId = null;
      }
      this.socket = null;
      if (NO_RECONNECT_CODES.has(event.code)) {
        this.emit({
          kind: "status",
          status: {
            kind: "disconnected",
            reason: `WebSocket closed with code ${event.code}`,
            since: new Date().toISOString(),
            failed_attempts: this.reconnectAttempt,
          },
        });
        return;
      }
      this.scheduleReconnect();
    };
  }
}
