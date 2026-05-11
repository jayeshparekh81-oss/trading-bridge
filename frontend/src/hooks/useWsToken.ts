/**
 * useWsToken — fetch + auto-refresh the 15-min chart-WS JWT.
 *
 * Refresh schedule (R3 — token-refresh-=-reconnect):
 *   - On mount: fetch token immediately.
 *   - Every 12 min (3-min grace before the 15-min server TTL),
 *     fetch a fresh one.
 *   - On unmount: clear the interval.
 *
 * The hook exposes ``token`` (current JWT or ``null`` while loading
 * + first error), ``error`` (last fetch error or ``null``), and a
 * ``version`` counter that increments on each successful refresh.
 * The WS hook subscribes to ``version`` to know when to reconnect
 * with the new token.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { fetchWsToken } from "@/lib/chart/api";

const REFRESH_INTERVAL_MS = 12 * 60 * 1_000; // 12 minutes

export interface UseWsTokenState {
  token: string | null;
  error: Error | null;
  /** Monotonically increasing — bumps each time a NEW token is set. */
  version: number;
  /** True while the first fetch is in flight. */
  isLoading: boolean;
  /**
   * Day-4 R1: ``true`` once two CONSECUTIVE token fetches have
   * failed. The chart UI uses this to:
   *   - render the "session expired" banner with the login CTA
   *   - tell ``useChartWebSocket`` to stop trying to reconnect
   * Reset to ``false`` by any subsequent successful fetch.
   */
  sessionExpired: boolean;
}

export interface UseWsTokenOptions {
  /** Skip the fetch entirely. Used by tests + mock harnesses. */
  enabled?: boolean;
}

export function useWsToken(
  opts: UseWsTokenOptions = {},
): UseWsTokenState {
  const enabled = opts.enabled ?? true;
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [version, setVersion] = useState(0);
  const [isLoading, setIsLoading] = useState(enabled);
  const [sessionExpired, setSessionExpired] = useState(false);

  // Strict-Mode safety: bail out of stale-async callbacks if the
  // component remounts (R2 pattern: capture a per-effect "alive" flag).
  const isAlive = useRef(true);
  // R1: count consecutive fetch failures. A single network blip
  // doesn't flip the user into the "session expired" UX — only two
  // failures in a row do (retry-once-then-banner per the senior-
  // review decision).
  const consecutiveFailures = useRef(0);

  const refresh = useCallback(async () => {
    try {
      const resp = await fetchWsToken();
      if (!isAlive.current) return;
      setToken(resp.token);
      setError(null);
      setVersion((v) => v + 1);
      consecutiveFailures.current = 0;
      setSessionExpired(false);
    } catch (err) {
      if (!isAlive.current) return;
      setError(
        err instanceof Error ? err : new Error("ws-token fetch failed"),
      );
      consecutiveFailures.current += 1;
      if (consecutiveFailures.current >= 2) {
        setSessionExpired(true);
      }
    } finally {
      if (isAlive.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false);
      return;
    }
    isAlive.current = true;
    void refresh();
    const id = setInterval(() => {
      void refresh();
    }, REFRESH_INTERVAL_MS);
    return () => {
      isAlive.current = false;
      clearInterval(id);
    };
  }, [enabled, refresh]);

  return { token, error, version, isLoading, sessionExpired };
}
