"use client";

/**
 * Safety bar — Rok do · Sab band · Settings · Bahar. ALWAYS visible at every
 * level (C5): fixed at the bottom on a phone, in the top-right on desktop.
 * The two dangerous ones ask "Haan?" first; the sentence says exactly what
 * will happen in plain words. Callbacks come in as props so the bar renders
 * (and is tested) without any network.
 */

import { useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { PauseCircle, OctagonX, Settings, LogOut, Loader2 } from "lucide-react";
import type { Lang } from "@/contexts/LanguageContext";
import { t } from "@/lib/simple/copy";
import { cn } from "@/lib/utils";

export interface SafetyBarProps {
  lang: Lang;
  /** Pause every running strategy/subscription. Resolves to a message to show. */
  onPause: () => Promise<string>;
  /** Close everything (the kill switch). Resolves to a message to show. */
  onStopAll: () => Promise<string>;
  onLogout: () => void;
  /** Placement: "bottom" (phone) or "top" (desktop). Default: both via CSS. */
  className?: string;
}

type Pending = "pause" | "stop" | null;

export function SafetyBar(p: SafetyBarProps) {
  const [confirm, setConfirm] = useState<Pending>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const reduce = useReducedMotion();
  const L = (k: Parameters<typeof t>[1]) => t(p.lang, k);

  async function run(kind: "pause" | "stop") {
    setBusy(true);
    try {
      const msg = kind === "pause" ? await p.onPause() : await p.onStopAll();
      setDone(msg);
    } catch {
      setDone(kind === "pause" ? L("safety_pause_hint") : L("safety_stop_all_hint"));
    } finally {
      setBusy(false);
      setConfirm(null);
      setTimeout(() => setDone(null), 4000);
    }
  }

  const btn =
    "flex flex-col items-center justify-center gap-1 rounded-xl px-2 py-2 text-[11px] font-semibold leading-none min-w-[64px] transition-colors";

  return (
    <>
      <nav
        aria-label="safety"
        data-testid="safety-bar"
        className={cn(
          "fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-[#0A0E1A]/95 backdrop-blur px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-2",
          "md:inset-x-auto md:bottom-auto md:top-3 md:right-4 md:rounded-2xl md:border md:px-2 md:py-1.5",
          p.className,
        )}
      >
        <div className="mx-auto flex max-w-md items-center justify-between gap-1 md:max-w-none md:gap-1">
          <button
            type="button"
            data-testid="safety-pause"
            onClick={() => setConfirm("pause")}
            title={L("safety_pause_hint")}
            className={cn(btn, "text-amber-300 hover:bg-amber-400/10")}
          >
            <PauseCircle className="h-6 w-6" aria-hidden="true" />
            {L("safety_pause")}
          </button>
          <button
            type="button"
            data-testid="safety-stop-all"
            onClick={() => setConfirm("stop")}
            title={L("safety_stop_all_hint")}
            className={cn(btn, "text-loss hover:bg-loss/10")}
          >
            <OctagonX className="h-6 w-6" aria-hidden="true" />
            {L("safety_stop_all")}
          </button>
          <Link href="/settings" data-testid="safety-settings" className={cn(btn, "text-foreground/80 hover:bg-white/5")}>
            <Settings className="h-6 w-6" aria-hidden="true" />
            {L("safety_settings")}
          </Link>
          <button
            type="button"
            data-testid="safety-logout"
            onClick={p.onLogout}
            className={cn(btn, "text-foreground/80 hover:bg-white/5")}
          >
            <LogOut className="h-6 w-6" aria-hidden="true" />
            {L("safety_logout")}
          </button>
        </div>
      </nav>

      <AnimatePresence>
        {confirm && (
          <motion.div
            key="confirm"
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-end md:items-center justify-center bg-black/60 p-4"
            role="dialog"
            aria-modal="true"
            data-testid="safety-confirm"
          >
            <motion.div
              initial={reduce ? false : { y: 24, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: 24, opacity: 0 }}
              transition={{ duration: 0.25, ease: "easeOut" }}
              className={cn(
                "glass w-full max-w-md rounded-2xl p-5 border",
                confirm === "stop" ? "border-loss/50" : "border-amber-300/40",
              )}
            >
              <p className="text-lg font-bold text-foreground">
                {confirm === "stop" ? L("safety_stop_all") : L("safety_pause")}
              </p>
              <p className="mt-2 text-sm text-foreground/85">
                {confirm === "stop" ? L("safety_confirm_stop_all") : L("safety_confirm_pause")}
              </p>
              <div className="mt-4 flex gap-2">
                <button
                  type="button"
                  disabled={busy}
                  data-testid="safety-confirm-yes"
                  onClick={() => run(confirm)}
                  className={cn(
                    "flex-1 rounded-full px-4 py-3 text-base font-bold text-[#0A0E1A]",
                    confirm === "stop" ? "bg-loss" : "bg-amber-300",
                  )}
                >
                  {busy ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : L("safety_yes")}
                </button>
                <button
                  type="button"
                  disabled={busy}
                  data-testid="safety-confirm-no"
                  onClick={() => setConfirm(null)}
                  className="flex-1 rounded-full border border-white/15 px-4 py-3 text-base font-semibold text-foreground"
                >
                  {L("safety_no")}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {done && (
          <motion.p
            key="done"
            initial={reduce ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="fixed left-1/2 -translate-x-1/2 bottom-24 md:bottom-auto md:top-20 z-50 rounded-full bg-[#0F1629] border border-white/15 px-4 py-2 text-sm text-foreground shadow-lg"
            data-testid="safety-done"
            role="status"
          >
            {done}
          </motion.p>
        )}
      </AnimatePresence>
    </>
  );
}
