"use client";

import { useEffect, useState } from "react";

export type SystemMode = {
  paper_mode: boolean;
  kill_switch_check_enabled: boolean;
  circuit_breaker_enabled: boolean;
  /**
   * ISO 8601 instant the platform's record starts from, e.g.
   * "2026-09-01T00:00:00+05:30". `null` means no cut-off is being applied.
   *
   * OPTIONAL on purpose: a backend that predates the field omits it, and an
   * absent field must read as "we have not been told", never as a date. The
   * ONE consumer is `useTrackingEpoch` in `@/lib/tracking-epoch`, which turns
   * all three of null / absent / unreadable into silence.
   */
  tracking_epoch?: string | null;
};

const POLL_INTERVAL_MS = 5 * 60 * 1000; // 5 min

// Hotfix 2026-05-17: hardcoded production fallback. See
// WS_URL_FIX_DIAGNOSIS.md. Env var still takes precedence when set.
const BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : "https://api.tradetri.com/api";

/**
 * useSystemMode — polls ``GET /api/system/mode`` every 5 min for the
 * platform's master safety toggles. Same endpoint backs the dashboard's
 * PaperModeBanner.
 *
 * Returns ``null`` while loading or on persistent failure — consumers
 * should treat ``null`` as "unknown" and either disable live actions
 * defensively or wait for the next poll.
 *
 * Safe to call without authentication — the endpoint exposes only
 * boolean flags by design (no secrets, no PII).
 */
export function useSystemMode(): SystemMode | null {
  const [mode, setMode] = useState<SystemMode | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${BASE}/system/mode`, { cache: "no-store" });
        if (!res.ok) return;
        const data: SystemMode = await res.json();
        if (!cancelled) setMode(data);
      } catch {
        // Network blip — keep last known state, retry next tick.
      }
    }

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return mode;
}
