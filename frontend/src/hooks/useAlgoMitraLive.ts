"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useApi } from "@/shared/api/use-api";
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
  deriveTodayPnl,
  getNotifMode,
  purgeLegacyBaselines,
  recordDismissal,
  recordReaction,
  type CurveRow,
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
  /**
   * CUMULATIVE P&L since the tracking cut-off. Deliberately UNUSED here.
   *
   * Reading this and subtracting a stored morning snapshot is exactly what
   * printed "🚀 ₹1,95,831! Killer day." over a loss on 2026-09-09: the
   * cut-off moved the series under the snapshot. Today's number comes from
   * `curve` — today's own rows — and must keep coming from there.
   */
  total_pnl: string;
  win_rate: number;
  /** Priced round trips, oldest-first, already cut-off filtered server-side. */
  curve?: CurveRow[] | null;
}

export interface UseAlgoMitraLive {
  /** Current toast text (null when nothing is showing). */
  message: string | null;
  /** Hide the current toast — also records a dismissal for blackout logic. */
  dismiss: () => void;
}

/**
 * Polls trade-stats every 60s, derives TODAY's P&L from the `curve` rows in
 * that same response, picks an emotional reaction, and surfaces it as a
 * toast.
 *
 * Mounted once at the dashboard layout level so all dashboard pages
 * share a single poller. Unmounting clears the timer.
 *
 * THREE RULES THIS HOOK EXISTS TO KEEP
 * ────────────────────────────────────
 * 1. **Derive, never subtract across time.** `deriveTodayPnl` sums today's
 *    own rows. No baseline, no localStorage, nothing to go stale.
 * 2. **Silence is not zero.** `deriveTodayPnl` returns null when the day
 *    holds no PRICED closes — which is true right now of all three post-cut
 *    positions (unpriced / `human_interfered`). The coach then says NOTHING.
 *    It must never fall back to 0 and announce a flat day.
 * 3. **Speak only when the band CHANGES.** The reaction effect used to key
 *    on `[data]`, a fresh object every 60s, and "profit-huge" is
 *    `important: true` — so it bypassed the cooldown AND the dismissal
 *    blackout and re-fired every single minute, with dismissal doing
 *    nothing. Now the effect keys on the derived PRIMITIVES and a
 *    band-change check gates the speech, so one band = at most one toast.
 */
export function useAlgoMitraLive(): UseAlgoMitraLive {
  const { data } = useApi<TradeStatsResponse>(
    "/users/me/trades/stats",
    null,
    POLL_MS,
  );

  const [message, setMessage] = useState<string | null>(null);
  /** Previous day-P&L — used to detect the sign-flip that means "recovery". */
  const prevAmountRef = useRef<number | null>(null);
  /** The band we last SPOKE. Same band again → stay quiet. */
  const spokenBandRef = useRef<ReactionTriggerId | null>(null);
  /** Trigger id of the currently-shown toast (for dismissal recording). */
  const liveTriggerRef = useRef<ReactionTriggerId | null>(null);
  /** Auto-dismiss timer handle. */
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // One-shot cleanup of the deleted baseline mechanism's localStorage keys.
  useEffect(() => {
    purgeLegacyBaselines();
  }, []);

  // Today's P&L, from today's own rows. null = we have nothing to say.
  const today = useMemo(() => deriveTodayPnl(data?.curve ?? null), [data]);
  // Primitives, so the effect below does not re-run on every poll's new
  // object identity — the repeat-toast half of the bug. `rows` earns its
  // place beside `amount`: two different sets of closes can net the same
  // rupee figure, and that is a real change in the day the effect should
  // reconsider (the band-change check then decides whether to speak).
  const amount = today ? today.amount : null;
  const rows = today ? today.rows : 0;

  // Drive the reaction picker when today's number actually moves.
  useEffect(() => {
    // Nothing priced closed today (or we could not read the day): SILENCE.
    // Reset, so a later first close of the day is not read as a "recovery"
    // from a number that belongs to a different day.
    if (amount === null) {
      prevAmountRef.current = null;
      spokenBandRef.current = null;
      return;
    }

    const trigger = selectTrigger(amount, prevAmountRef.current);
    prevAmountRef.current = amount;

    // Back inside the quiet middle — re-arm, so re-entering a band speaks.
    if (trigger === null) {
      spokenBandRef.current = null;
      return;
    }
    // Same band as the toast we already showed — say it once, not every minute.
    if (spokenBandRef.current === trigger) return;

    const mode = getNotifMode();
    if (
      !canShowReaction(
        { triggerId: trigger, isImportant: isImportantTrigger(trigger) },
        mode,
      )
    ) {
      // Gated, not spoken — leave the band un-marked so it can still be
      // said once the gate opens.
      return;
    }

    const lang = getStoredLang();
    const tod = getTimeOfDay();
    const rendered = renderReaction(trigger, amount, lang, tod);
    // The polarity guard refused this pairing. There is no fallback
    // sentence — the wrong one is the only other option. Say nothing.
    if (rendered === null) return;

    spokenBandRef.current = trigger;
    setMessage(rendered.message);
    liveTriggerRef.current = trigger;
    recordReaction(trigger);

    // Auto-dismiss without recording a manual dismissal.
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setMessage(null);
      liveTriggerRef.current = null;
    }, TOAST_DURATION_MS);
  }, [amount, rows]);

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
