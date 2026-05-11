/**
 * useChartWebSocket — live chart-feed WebSocket with reconnect,
 * heartbeat, and Strict-Mode hygiene.
 *
 * Lifecycle contract (R2 — React 19 dev runs effects twice):
 *   - The socket instance lives in a ``useRef``.
 *   - The connect effect is idempotent: if a socket exists and is
 *     open/connecting, it skips. If one exists in any other state,
 *     it's closed before a new one is created.
 *   - The cleanup function ALWAYS closes the current socket and
 *     clears all timers. Dev hot-reload cannot leak connections.
 *
 * Reconnect contract (mirrors backend):
 *   - Exponential backoff: ``1s → 2s → 4s → 8s → 16s → 32s``, cap 60s.
 *   - ±25% full jitter on each delay.
 *   - Status stays ``connecting`` while retries happen silently.
 *   - The backend will emit a ``broker_disconnected`` envelope after
 *     its own 5-min threshold; the hook switches status to
 *     ``disconnected`` on receipt and back to ``open`` on
 *     ``broker_reconnected``.
 *
 * Token-refresh contract (R3):
 *   - The hook takes a ``token`` string + a ``tokenVersion`` counter.
 *   - When ``tokenVersion`` increments, the hook closes the current
 *     socket and reconnects with the new token. ~1s gap accepted
 *     for v1; graceful overlap-swap is Day-4 polish.
 *
 * Mock contract (R6):
 *   - When ``NEXT_PUBLIC_USE_MOCK=true``, the hook subscribes to an
 *     in-memory ``createMockWsServer`` emitter instead of opening a
 *     real WebSocket. Same envelope shapes, same handlers.
 */

"use client";

import { useEffect, useReducer, useRef } from "react";

import { buildChartWsUrl } from "@/lib/chart/api";
import { createMockWsServer, isMockEnabled } from "@/lib/chart/mock_data";
import {
  isBrokerDisconnectedEnvelope,
  isBrokerReconnectedEnvelope,
  isCandleEnvelope,
  parseCandle,
  type Candle,
  type ChartEnvelope,
  type ConnectionStatus,
  type Timeframe,
} from "@/lib/chart/types";

// ═══════════════════════════════════════════════════════════════════════
// Tuning constants (kept identical to backend so behaviour aligns)
// ═══════════════════════════════════════════════════════════════════════

const RECONNECT_BASE_DELAY_MS = 1_000;
const RECONNECT_MAX_DELAY_MS = 60_000;
const RECONNECT_JITTER_FACTOR = 0.25;
const HEARTBEAT_INTERVAL_MS = 20_000;
/** Close codes emitted by the backend that should NOT trigger reconnect. */
const NO_RECONNECT_CODES = new Set([4400, 4401]); // bad params / auth

// ═══════════════════════════════════════════════════════════════════════
// Reducer state — candle array + connection status
// ═══════════════════════════════════════════════════════════════════════
//
// The reducer is the single place candles are mutated. Two ops:
//   - ``init``     replaces the array (used by useChartHistory on mount
//                   + on symbol/timeframe change).
//   - ``upsert``   replaces the last candle if its ``time`` matches the
//                   incoming one (= same bucket update), otherwise
//                   appends. Pre-bucket-roll history is immutable.

interface State {
  candles: Candle[];
  status: ConnectionStatus;
}

type Action =
  | { type: "init"; candles: Candle[] }
  | { type: "upsert"; candle: Candle }
  | { type: "connecting" }
  | { type: "open" }
  | {
      type: "disconnected";
      reason: string;
      since: string;
      failed_attempts: number;
    };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "init":
      return { ...state, candles: action.candles };
    case "upsert": {
      const arr = state.candles;
      const tail = arr[arr.length - 1];
      if (tail && tail.time === action.candle.time) {
        // Same bucket — replace.
        return { ...state, candles: [...arr.slice(0, -1), action.candle] };
      }
      if (tail && tail.time > action.candle.time) {
        // Out-of-order frame (unlikely; ignore to keep array sorted).
        return state;
      }
      return { ...state, candles: [...arr, action.candle] };
    }
    case "connecting":
      return { ...state, status: { kind: "connecting" } };
    case "open":
      return { ...state, status: { kind: "open" } };
    case "disconnected":
      return {
        ...state,
        status: {
          kind: "disconnected",
          reason: action.reason,
          since: action.since,
          failed_attempts: action.failed_attempts,
        },
      };
  }
}

const INITIAL_STATE: State = {
  candles: [],
  status: { kind: "connecting" },
};

// ═══════════════════════════════════════════════════════════════════════
// Backoff helper — exported for unit tests
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
  const jitter =
    (random() * 2 - 1) * base * RECONNECT_JITTER_FACTOR;
  return Math.max(0, base + jitter);
}

// ═══════════════════════════════════════════════════════════════════════
// Hook
// ═══════════════════════════════════════════════════════════════════════

export interface UseChartWebSocketOptions {
  symbol: string;
  timeframe: Timeframe;
  /** Current JWT — when null, the hook holds open the
   *  ``connecting`` state and never tries to connect. */
  token: string | null;
  /** Monotonic counter that bumps on each fresh token. R3 — the
   *  hook reconnects when this changes. */
  tokenVersion: number;
  /** Initial candle array from REST. Replays into the reducer
   *  via ``init`` on each (symbol, timeframe) change. */
  initialCandles: Candle[];
  /** Override the mock toggle (test injection point). */
  forceMock?: boolean;
}

export interface UseChartWebSocketState {
  candles: Candle[];
  status: ConnectionStatus;
}

export function useChartWebSocket(
  opts: UseChartWebSocketOptions,
): UseChartWebSocketState {
  const {
    symbol,
    timeframe,
    token,
    tokenVersion,
    initialCandles,
    forceMock,
  } = opts;

  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);

  // ── Socket + timer refs (R2 — Strict Mode safety) ──────────────────
  const socketRef = useRef<WebSocket | null>(null);
  const mockServerRef = useRef<ReturnType<typeof createMockWsServer> | null>(
    null,
  );
  const reconnectAttemptRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );
  const heartbeatTimeoutRef = useRef<ReturnType<typeof setInterval> | null>(
    null,
  );
  const isUnmountedRef = useRef(false);

  // ── Reset candle state when the seed array's reference changes ────
  // We track the seed by ref rather than putting it in a dep array
  // because every render of the parent passes a new array reference
  // (orchestrator combines history + WS state). A dep-array approach
  // would re-init on every render — infinite loop. The ref compare
  // dispatches exactly once per genuine seed change, including the
  // (symbol, timeframe) transitions handled by the orchestrator.
  const lastSeedRef = useRef<Candle[] | null>(null);
  useEffect(() => {
    if (lastSeedRef.current !== initialCandles) {
      lastSeedRef.current = initialCandles;
      dispatch({ type: "init", candles: initialCandles });
    }
  });

  // ── Connect / reconnect / cleanup ──────────────────────────────────
  useEffect(() => {
    isUnmountedRef.current = false;
    const useMock = forceMock ?? isMockEnabled();

    function clearTimers() {
      if (reconnectTimeoutRef.current !== null) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (heartbeatTimeoutRef.current !== null) {
        clearInterval(heartbeatTimeoutRef.current);
        heartbeatTimeoutRef.current = null;
      }
    }

    function closeExisting() {
      clearTimers();
      if (socketRef.current) {
        // Avoid the close-handler triggering another reconnect.
        socketRef.current.onclose = null;
        socketRef.current.onerror = null;
        try {
          socketRef.current.close();
        } catch {
          /* close-time errors must not propagate */
        }
        socketRef.current = null;
      }
      if (mockServerRef.current) {
        mockServerRef.current.stop();
        mockServerRef.current = null;
      }
    }

    function handleEnvelope(env: ChartEnvelope) {
      if (isUnmountedRef.current) return;
      if (isCandleEnvelope(env)) {
        try {
          dispatch({ type: "upsert", candle: parseCandle(env.data) });
        } catch {
          // Malformed wire candle — drop the frame.
        }
        return;
      }
      if (isBrokerDisconnectedEnvelope(env)) {
        dispatch({
          type: "disconnected",
          reason: env.reason,
          since: env.since,
          failed_attempts: env.failed_attempts,
        });
        return;
      }
      if (isBrokerReconnectedEnvelope(env)) {
        dispatch({ type: "open" });
        return;
      }
      // heartbeat → no-op (presence of any frame already keeps the
      // socket layer happy; we don't need to track liveness here
      // since the browser does).
    }

    function startHeartbeat(ws: WebSocket) {
      heartbeatTimeoutRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          try {
            // Empty ping payload — Lightweight Charts doesn't care;
            // backend's read loop sees a 'message' event and counts
            // the connection as alive.
            ws.send("ping");
          } catch {
            /* send-on-closing edge — handled by onclose */
          }
        }
      }, HEARTBEAT_INTERVAL_MS);
    }

    function scheduleReconnect() {
      if (isUnmountedRef.current) return;
      const attempt = ++reconnectAttemptRef.current;
      const delay = reconnectDelayMs(attempt);
      reconnectTimeoutRef.current = setTimeout(() => {
        reconnectTimeoutRef.current = null;
        connect();
      }, delay);
    }

    function connect() {
      if (isUnmountedRef.current) return;
      if (!token) return; // wait for token to land
      // Idempotency guard (R2): if a socket is already alive, do
      // nothing. This handles Strict Mode's double-effect run.
      if (
        socketRef.current &&
        (socketRef.current.readyState === WebSocket.CONNECTING ||
          socketRef.current.readyState === WebSocket.OPEN)
      ) {
        return;
      }

      dispatch({ type: "connecting" });

      if (useMock) {
        // ── Mock path (R6) ────────────────────────────────────────
        const server = createMockWsServer({ symbol, timeframe });
        server.onMessage(handleEnvelope);
        server.start();
        mockServerRef.current = server;
        reconnectAttemptRef.current = 0;
        dispatch({ type: "open" });
        return;
      }

      // ── Real WebSocket path ─────────────────────────────────────
      const url = buildChartWsUrl({ symbol, timeframe, token });
      let ws: WebSocket;
      try {
        ws = new WebSocket(url);
      } catch {
        // Construction failure (e.g. bad URL) — schedule retry.
        scheduleReconnect();
        return;
      }
      socketRef.current = ws;

      ws.onopen = () => {
        if (isUnmountedRef.current) {
          try {
            ws.close();
          } catch {
            /* idem */
          }
          return;
        }
        reconnectAttemptRef.current = 0;
        dispatch({ type: "open" });
        startHeartbeat(ws);
      };

      ws.onmessage = (event) => {
        if (isUnmountedRef.current) return;
        try {
          const env = JSON.parse(event.data) as ChartEnvelope;
          handleEnvelope(env);
        } catch {
          // Non-JSON payload — drop.
        }
      };

      ws.onerror = () => {
        // ``onclose`` fires right after; reconnect is scheduled there.
      };

      ws.onclose = (event) => {
        if (isUnmountedRef.current) return;
        if (heartbeatTimeoutRef.current !== null) {
          clearInterval(heartbeatTimeoutRef.current);
          heartbeatTimeoutRef.current = null;
        }
        socketRef.current = null;
        if (NO_RECONNECT_CODES.has(event.code)) {
          // Bad token / bad params — don't loop forever.
          dispatch({
            type: "disconnected",
            reason: `WebSocket closed with code ${event.code}`,
            since: new Date().toISOString(),
            failed_attempts: reconnectAttemptRef.current,
          });
          return;
        }
        // All other closes → silent reconnect via exp backoff.
        scheduleReconnect();
      };
    }

    closeExisting(); // Always start fresh — Strict-Mode-safe.
    connect();

    return () => {
      isUnmountedRef.current = true;
      closeExisting();
    };
    // ``tokenVersion`` in the dep array triggers reconnect on refresh
    // (R3). The other deps (``symbol``, ``timeframe``, ``token``,
    // ``forceMock``) all logically invalidate the connection too.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, timeframe, token, tokenVersion, forceMock]);

  return { candles: state.candles, status: state.status };
}
