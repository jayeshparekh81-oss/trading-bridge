/**
 * useChartWebSocket — React binding around ``ChartWsTransport``.
 *
 * The complex lifecycle (connect / reconnect / heartbeat /
 * sessionExpired guard / token refresh / mock vs real) lives in
 * ``ChartWsTransport`` so it can be unit-tested without React, jsdom,
 * or ``renderHook``. This hook owns three jobs only:
 *
 *   1. Create exactly one transport per (symbol, timeframe, forceMock)
 *      — when any of those changes, close the old transport and
 *      construct a new one. Mount + Strict-Mode safe.
 *   2. Translate transport events into reducer dispatches so React
 *      consumers see ``{ candles, status }`` updates.
 *   3. Forward prop changes that do NOT warrant a fresh transport:
 *      ``token`` / ``tokenVersion`` go through ``updateToken``,
 *      ``sessionExpired`` through ``setSessionExpired``.
 *
 * External API is unchanged from the Day-5 hook — same props, same
 * return shape. Consumers (e.g. ChartContainer) need no edits.
 */

"use client";

import { useEffect, useReducer, useRef } from "react";

import { ChartWsTransport } from "@/lib/chart/chart_ws_transport";
import type { Candle, ConnectionStatus, Timeframe } from "@/lib/chart/types";

// Re-export the backoff helper so existing pure-function tests keep
// working without a second import path.
export { reconnectDelayMs } from "@/lib/chart/chart_ws_transport";

// ═══════════════════════════════════════════════════════════════════════
// Reducer
// ═══════════════════════════════════════════════════════════════════════

interface State {
  candles: Candle[];
  status: ConnectionStatus;
}

type Action =
  | { type: "init"; candles: Candle[] }
  | { type: "upsert"; candle: Candle }
  | { type: "status"; status: ConnectionStatus };

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "init":
      return { ...state, candles: action.candles };
    case "upsert": {
      const arr = state.candles;
      const tail = arr[arr.length - 1];
      if (tail && tail.time === action.candle.time) {
        return { ...state, candles: [...arr.slice(0, -1), action.candle] };
      }
      if (tail && tail.time > action.candle.time) {
        return state;
      }
      return { ...state, candles: [...arr, action.candle] };
    }
    case "status":
      return { ...state, status: action.status };
  }
}

const INITIAL_STATE: State = {
  candles: [],
  status: { kind: "connecting" },
};

// ═══════════════════════════════════════════════════════════════════════
// Hook
// ═══════════════════════════════════════════════════════════════════════

export interface UseChartWebSocketOptions {
  symbol: string;
  timeframe: Timeframe;
  token: string | null;
  tokenVersion: number;
  initialCandles: Candle[];
  sessionExpired?: boolean;
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
    sessionExpired = false,
    forceMock,
  } = opts;

  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const transportRef = useRef<ChartWsTransport | null>(null);

  // Mirror token/sessionExpired into refs so the mount effect can read
  // the current values when constructing the transport without taking
  // a dep on them (token + sessionExpired have their own effects).
  const tokenRef = useRef(token);
  const tokenVersionRef = useRef(tokenVersion);
  const sessionExpiredRef = useRef(sessionExpired);
  tokenRef.current = token;
  tokenVersionRef.current = tokenVersion;
  sessionExpiredRef.current = sessionExpired;

  // ── Seed reset ────────────────────────────────────────────────────
  // Ref-compare instead of dep array: the parent passes a fresh
  // ``initialCandles`` reference on every render, so a dep-array
  // approach would loop. Compare-by-reference dispatches exactly once
  // per genuine seed change.
  const lastSeedRef = useRef<Candle[] | null>(null);
  useEffect(() => {
    if (lastSeedRef.current !== initialCandles) {
      lastSeedRef.current = initialCandles;
      dispatch({ type: "init", candles: initialCandles });
    }
  });

  // ── Transport lifecycle ────────────────────────────────────────────
  // Recreate on (symbol, timeframe, forceMock) change. Token + version
  // are handled separately so a token refresh swaps the socket inside
  // the same transport (no React-level remount).
  useEffect(() => {
    const transport = new ChartWsTransport({ useMock: forceMock });
    transportRef.current = transport;

    const unsub = transport.subscribe((event) => {
      if (event.kind === "candle") {
        dispatch({ type: "upsert", candle: event.candle });
        return;
      }
      dispatch({ type: "status", status: event.status });
    });

    transport.setSessionExpired(sessionExpiredRef.current);
    transport.open(
      { symbol, timeframe, token: tokenRef.current },
      tokenVersionRef.current,
    );

    return () => {
      unsub();
      transport.close();
      if (transportRef.current === transport) {
        transportRef.current = null;
      }
    };
  }, [symbol, timeframe, forceMock]);

  // ── Token refresh ──────────────────────────────────────────────────
  // The mount effect already opens with the initial token, so we
  // gate this effect on a version mismatch to avoid a redundant
  // close-and-reopen on the very first render.
  useEffect(() => {
    const transport = transportRef.current;
    if (!transport) return;
    if (transport.getTokenVersion() === tokenVersion) return;
    transport.updateToken(token, tokenVersion);
  }, [token, tokenVersion]);

  // ── Session-expired guard (R1) ─────────────────────────────────────
  useEffect(() => {
    transportRef.current?.setSessionExpired(sessionExpired);
  }, [sessionExpired]);

  return { candles: state.candles, status: state.status };
}
