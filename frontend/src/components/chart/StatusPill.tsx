/**
 * StatusPill — always-visible WS connection indicator in the chart
 * header. Three visual states match ``ConnectionStatus.kind``:
 *
 *   - ``open``                                  → green  · "Live"
 *   - ``connecting`` (reconnectAttempt > 0)     → amber  · "Reconnecting in Xs..."
 *   - ``connecting`` (reconnectAttempt == 0)    → amber  · "Connecting..."
 *   - ``disconnected``                          → red    · "Disconnected" + manual button
 *
 * Sustained-failure escape hatch (B8): once the exp-backoff
 * sequence has clocked enough attempts to plateau at the 60s cap
 * (attempt >= ``MANUAL_RECONNECT_ATTEMPT_THRESHOLD``), the manual
 * "Reconnect now" button surfaces alongside the reconnecting label
 * — gives the user a way to skip the wait without restarting the
 * tab.
 *
 * The countdown is an APPROXIMATION: the transport's real timer
 * runs server-side of this component (i.e. inside ChartWsTransport)
 * with jitter we can't introspect. We compute the expected delay
 * via ``reconnectDelayMs(attempt)`` at each status transition and
 * tick down a local clock. The displayed seconds may drift slightly
 * from the actual fire time — that's acceptable for a UX hint.
 *
 * No toast is fired from here — A4 already handles the disconnected
 * toast via ChartContainer's effect. The pill is a SECOND surface
 * for the same information, intentionally non-blocking.
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { Wifi, WifiOff, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { reconnectDelayMs } from "@/lib/chart/chart_ws_transport";
import type { ConnectionStatus } from "@/lib/chart/types";

// Attempt # at which the exp-backoff sequence first hits the 60s
// cap (1s, 2s, 4s, 8s, 16s, 32s, 60s — attempt 7 hits cap). After
// this we consider the connection "sustained failure" and reveal
// the manual reconnect button even in the connecting state.
const MANUAL_RECONNECT_ATTEMPT_THRESHOLD = 7;

export interface StatusPillProps {
  status: ConnectionStatus;
  reconnectAttempt: number;
  /** B8: invoked when the user clicks "Reconnect now". */
  onManualReconnect: () => void;
}

export function StatusPill({
  status,
  reconnectAttempt,
  onManualReconnect,
}: StatusPillProps) {
  const countdownSec = useReconnectCountdown(status, reconnectAttempt);

  const showManualButton =
    status.kind === "disconnected" ||
    (status.kind === "connecting" &&
      reconnectAttempt >= MANUAL_RECONNECT_ATTEMPT_THRESHOLD);

  const variant = pillVariant(status);
  const label = pillLabel(status, reconnectAttempt, countdownSec);

  return (
    <div
      data-testid="chart-status-pill"
      data-state={variant.state}
      // Phase 4 mobile sizing — smaller padding + tighter gap on
      // < md so the pill doesn't dominate the mobile top bar. The
      // text label is hidden under sm: to leave only the dot +
      // icon on phones; the dot colour alone is enough to
      // communicate state at-a-glance.
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium md:gap-2 md:px-3 md:py-1 md:text-xs ${variant.classes}`}
    >
      <span
        aria-hidden="true"
        data-testid={`chart-status-dot-${variant.state}`}
        className={`h-2 w-2 rounded-full ${variant.dotClasses}`}
      />
      <span
        data-testid="chart-status-label"
        className="hidden sm:inline"
      >
        {label}
      </span>
      {variant.icon}
      {showManualButton && (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="ml-1 h-6 px-2 text-xs"
          onClick={onManualReconnect}
          data-testid="chart-status-manual-reconnect"
        >
          <RotateCw className="mr-1 h-3 w-3" />
          <span className="hidden sm:inline">Reconnect now</span>
          <span className="sm:hidden" aria-hidden="true">
            ↻
          </span>
        </Button>
      )}
    </div>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────

interface PillVariant {
  state: "live" | "connecting" | "disconnected";
  classes: string;
  dotClasses: string;
  icon: React.ReactNode;
}

function pillVariant(status: ConnectionStatus): PillVariant {
  if (status.kind === "open") {
    return {
      state: "live",
      classes: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
      dotClasses: "bg-emerald-400 animate-pulse",
      icon: <Wifi className="h-3 w-3" aria-hidden="true" />,
    };
  }
  if (status.kind === "disconnected") {
    return {
      state: "disconnected",
      classes: "border-red-500/40 bg-red-500/10 text-red-300",
      dotClasses: "bg-red-500",
      icon: <WifiOff className="h-3 w-3" aria-hidden="true" />,
    };
  }
  return {
    state: "connecting",
    classes: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    dotClasses: "bg-amber-400 animate-pulse",
    icon: null,
  };
}

function pillLabel(
  status: ConnectionStatus,
  reconnectAttempt: number,
  countdownSec: number | null,
): string {
  if (status.kind === "open") return "Live";
  if (status.kind === "disconnected") return "Disconnected";
  // connecting
  if (reconnectAttempt === 0) return "Connecting...";
  if (countdownSec !== null && countdownSec > 0) {
    return `Reconnecting in ${countdownSec}s...`;
  }
  return "Reconnecting...";
}

/**
 * Approximates the time-until-next-reconnect by:
 *   1. Capturing ``reconnectDelayMs(reconnectAttempt)`` at each
 *      (kind, attempt) transition.
 *   2. Ticking a local clock 4x/sec so the displayed integer
 *      seconds count down smoothly.
 *   3. Resetting when the status changes (e.g. open or
 *      disconnected) or the attempt increments to a new cycle.
 *
 * Returns ``null`` when not in a reconnecting state.
 */
function useReconnectCountdown(
  status: ConnectionStatus,
  reconnectAttempt: number,
): number | null {
  const [remaining, setRemaining] = useState<number | null>(null);
  const nextAtRef = useRef<number | null>(null);

  useEffect(() => {
    const isReconnecting =
      status.kind === "connecting" && reconnectAttempt > 0;

    if (!isReconnecting) {
      nextAtRef.current = null;
      setRemaining(null);
      return;
    }

    // Use the deterministic mean of the jittered backoff (no random
    // input) — the displayed value is a hint, not a contract.
    const delayMs = reconnectDelayMs(reconnectAttempt, () => 0.5);
    nextAtRef.current = Date.now() + delayMs;
    setRemaining(Math.max(0, Math.ceil(delayMs / 1000)));

    const intervalId = setInterval(() => {
      if (nextAtRef.current === null) return;
      const ms = nextAtRef.current - Date.now();
      setRemaining(Math.max(0, Math.ceil(ms / 1000)));
    }, 250);

    return () => {
      clearInterval(intervalId);
    };
  }, [status.kind, reconnectAttempt]);

  return remaining;
}
