"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";

/**
 * Connection status payload returned by ``GET /api/brokers/dhan/status``.
 *
 * Field shapes mirror the backend ``DhanStatusResponse`` model:
 *   - ``connected`` is the source-of-truth boolean.
 *   - ``label`` is null when no active credential exists.
 *   - ``last_updated`` is the ISO timestamp the cred row was created.
 *   - ``expires_estimate`` is a UI hint only — Dhan PATs can be 1d to
 *     1y at generation time and the real expiry is not exposed by
 *     Dhan after generation, so we surface the conservative 24h
 *     estimate the backend writes.
 */
export type DhanBrokerStatus = {
  connected: boolean;
  label: string | null;
  last_updated: string | null;
  expires_estimate: string | null;
};

/**
 * Three-state badge ``status`` derived from the wire payload:
 *
 *   - ``"connected"``     — active cred exists AND expires_estimate is
 *                            in the future (or absent).
 *   - ``"expired"``       — active cred exists BUT expires_estimate is
 *                            already in the past.
 *   - ``"not_connected"`` — no active cred, or the fetch hasn't landed
 *                            yet.
 *
 * Loading + persistent failure both collapse to ``"not_connected"``
 * so the broker card never reads "Connected" optimistically.
 */
export type BrokerBadgeStatus = "connected" | "expired" | "not_connected";

export type UseBrokerStatusResult = {
  status: BrokerBadgeStatus;
  lastUpdated: string | null;
  expiresAt: string | null;
  label: string | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
};

//: 60-second poll cadence per the spec. Matches the existing 60-second
//: ``now`` tick in brokers/page.tsx so the expiry badge flips on the
//: same interval the page already uses.
const POLL_INTERVAL_MS = 60_000;

/**
 * Poll the per-user Dhan broker status. Returns a derived three-state
 * badge value plus the underlying timestamps and a manual ``refetch``
 * the modal can fire after a successful token update.
 *
 * Behaviour:
 *   - Initial render fires one fetch immediately.
 *   - 60-second polling tick fetches in the background.
 *   - 401 from the API short-circuits to ``not_connected`` without
 *     bubbling the error — callers see the badge and can decide to
 *     redirect to login at a higher level.
 *   - Any other error path leaves ``status`` unchanged (last-known)
 *     and surfaces a string via ``error`` for an in-modal banner.
 */
export function useBrokerStatus(): UseBrokerStatusResult {
  const [status, setStatus] = useState<DhanBrokerStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Trigger token — bumped by refetch() to re-run the effect without
  // tearing down the polling timer.
  const [tick, setTick] = useState<number>(0);
  // ``now`` underlies the connected-vs-expired badge derivation below.
  // We snapshot it in state and refresh every 60s so the derivation
  // stays pure during render — calling Date.now() at render time
  // breaks React's idempotency expectation (react-hooks/purity).
  const [now, setNow] = useState<number>(() => Date.now());

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function fetchStatus(): Promise<void> {
      try {
        const data = await api.get<DhanBrokerStatus>("/brokers/dhan/status");
        if (cancelled) return;
        setStatus(data);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        // 401 → user is unauthenticated; collapse to not_connected.
        // The api client triggers a token-refresh attempt on 401, so
        // by the time we land here the refresh has already failed.
        if (err instanceof ApiError && err.status === 401) {
          setStatus({
            connected: false,
            label: null,
            last_updated: null,
            expires_estimate: null,
          });
          setError(null);
        } else {
          const message =
            err instanceof ApiError ? err.detail : "Couldn't load broker status";
          setError(message);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchStatus();
    const id = window.setInterval(fetchStatus, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [tick]);

  // Derive the three-state badge from the wire payload + the wall
  // clock. Re-evaluated every render — cheap, no setState loop.
  let badge: BrokerBadgeStatus = "not_connected";
  if (status?.connected) {
    if (status.expires_estimate) {
      badge =
        new Date(status.expires_estimate).getTime() <= now
          ? "expired"
          : "connected";
    } else {
      badge = "connected";
    }
  }

  return {
    status: badge,
    lastUpdated: status?.last_updated ?? null,
    expiresAt: status?.expires_estimate ?? null,
    label: status?.label ?? null,
    loading,
    error,
    refetch,
  };
}
