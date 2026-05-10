"use client";

import { useEffect, useState } from "react";

type SystemMode = {
  paper_mode: boolean;
  kill_switch_check_enabled: boolean;
  circuit_breaker_enabled: boolean;
};

const POLL_INTERVAL_MS = 5 * 60 * 1000; // 5 min

const BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : "/api";

/**
 * PaperModeBanner — top-of-dashboard yellow strip that renders when the
 * backend reports `paper_mode=true`. Polls /api/system/mode every 5 min.
 *
 * Unauthenticated fetch by design — the endpoint exposes only public
 * boolean toggles, and the banner needs to render before/regardless of
 * auth state so a paper-mode test deployment is unmistakable on any page.
 *
 * Renders nothing while loading, on fetch failure, or when paper_mode is
 * false — the dashboard layout collapses to its normal state.
 */
export function PaperModeBanner() {
  const [paperMode, setPaperMode] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`${BASE}/system/mode`, { cache: "no-store" });
        if (!res.ok) return;
        const data: SystemMode = await res.json();
        if (!cancelled) setPaperMode(data.paper_mode);
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

  if (paperMode !== true) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="bg-yellow-400 text-yellow-950 px-4 py-2 text-center text-sm font-semibold border-b border-yellow-500"
    >
      📝 PAPER MODE — orders are simulated, no real broker calls
    </div>
  );
}
