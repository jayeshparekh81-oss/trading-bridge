"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useApi } from "@/lib/use-api";
import { getStoredLang } from "@/lib/language-detector";
import { getTimeOfDay } from "@/lib/algomitra-personality";
import {
  isImportantTrigger,
  renderReaction,
  selectTrigger,
  type ReactionTriggerId,
} from "@/lib/algomitra-reactions";
import {
  canShowReaction,
  getDailyBaseline,
  getNotifMode,
  recordDismissal,
  recordReaction,
} from "@/lib/pnl-tracker";

/**
 * Polling cadence for the live reaction layer.
 *
 * 60 seconds per spec — slow enough to avoid burning user attention,
 * fast enough that a real-time-feeling reaction lands within a minute
 * of the underlying trade close.
 */
const POLL_MS = 60_000;

/** How long a reaction stays visible before auto-fade (ms). */
const TOAST_DURATION_MS = 8_000;

interface TradeStatsResponse {
  total_trades: number;
  total_pnl: string;
  win_rate: number;
}

export interface UseAlgoMitraLive {
  /** Current toast text (null when nothing is showing). */
  message: string | null;
  /** Hide the current toast — also records a dismissal for blackout logic. */
  dismiss: () => void;
}

/**
 * Polls trade-stats every 60s, derives "today's running P&L" from
 * a daily IST baseline stored in localStorage, picks an emotional
 * reaction, and surfaces it as a toast.
 *
 * Mounted once at the dashboard layout level so all dashboard pages
 * share a single poller. Unmounting clears the timer.
 */
export function useAlgoMitraLive(): UseAlgoMitraLive {
  const { data } = useApi<TradeStatsResponse>(
    "/users/me/trades/stats",
    null,
    POLL_MS,
  );

  const [message, setMessage] = useState<string | null>(null);
  /** Most recent delta (today's P&L) — used to detect sign-flip recovery. */
  const prevDeltaRef = useRef<number | null>(null);
  /** Trigger id of the currently-shown toast (for dismissal recording). */
  const liveTriggerRef = useRef<ReactionTriggerId | null>(null);
  /** Auto-dismiss timer handle. */
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Drive the reaction picker whenever fresh stats arrive.
  useEffect(() => {
    if (!data) return;
    const total = Number(data.total_pnl);
    if (Number.isNaN(total)) return;

    const { baseline, isFirstReadToday } = getDailyBaseline(total);
    // Skip the very first read of the day — it just establishes baseline.
    if (isFirstReadToday) {
      prevDeltaRef.current = 0;
      return;
    }

    const delta = total - baseline;
    const trigger = selectTrigger(delta, prevDeltaRef.current);
    prevDeltaRef.current = delta;
    if (trigger === null) return;

    const mode = getNotifMode();
    if (
      !canShowReaction(
        { triggerId: trigger, isImportant: isImportantTrigger(trigger) },
        mode,
      )
    ) {
      return;
    }

    const lang = getStoredLang();
    const tod = getTimeOfDay();
    const rendered = renderReaction(trigger, delta, lang, tod);

    setMessage(rendered.message);
    liveTriggerRef.current = trigger;
    recordReaction(trigger);

    // Auto-dismiss without recording a manual dismissal.
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setMessage(null);
      liveTriggerRef.current = null;
    }, TOAST_DURATION_MS);
  }, [data]);

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const dismiss = useMemo(
    () => () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      // Manual dismissal counts toward the 3-strike blackout.
      if (liveTriggerRef.current && !isImportantTrigger(liveTriggerRef.current)) {
        recordDismissal();
      }
      setMessage(null);
      liveTriggerRef.current = null;
    },
    [],
  );

  return { message, dismiss };
}
