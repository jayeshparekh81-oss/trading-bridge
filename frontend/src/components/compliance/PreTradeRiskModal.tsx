/**
 * PreTradeRiskModal — fires once before a user's first live order.
 *
 * Standalone component. Mount it anywhere along the live-order entry
 * path and pass `open` / `onConfirm` / `onCancel`. The component
 * checks localStorage for a prior acknowledgment; if found, it
 * short-circuits by auto-invoking `onConfirm` so callers don't have
 * to re-run the gate logic themselves.
 *
 * Not wired into go-live-modal in this commit (go-live-modal is
 * out of scope for this branch). The mount + dispatch pattern is
 * a follow-up sprint.
 */

"use client";

import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  LS_KEY_PRE_TRADE_ACK,
  PRE_TRADE_COPY,
} from "@/lib/compliance/disclaimer-text";

export interface PreTradeRiskModalProps {
  open: boolean;
  lang?: "en" | "hi";
  onConfirm: () => void;
  onCancel: () => void;
}

function safeRead(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeWrite(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* quota / private mode — silently drop */
  }
}

/** Has the user already acknowledged the pre-trade modal in a prior
 *  session? Callers can use this to skip mounting the modal at all
 *  if they prefer. Re-export so tests can assert without re-deriving
 *  the localStorage key. */
export function hasAcknowledgedPreTrade(): boolean {
  return safeRead(LS_KEY_PRE_TRADE_ACK) !== null;
}

export function PreTradeRiskModal({
  open,
  lang = "hi",
  onConfirm,
  onCancel,
}: PreTradeRiskModalProps) {
  const [autoConfirmedOnce, setAutoConfirmedOnce] = useState(false);

  useEffect(() => {
    if (!open) return;
    // First-time-only contract: if the user has already acknowledged,
    // auto-confirm and let the caller proceed without re-prompting.
    if (!autoConfirmedOnce && hasAcknowledgedPreTrade()) {
      setAutoConfirmedOnce(true);
      onConfirm();
    }
  }, [open, autoConfirmedOnce, onConfirm]);

  // Don't render the modal chrome if it's closed OR already auto-confirmed.
  if (!open) return null;
  if (hasAcknowledgedPreTrade()) return null;

  const title = lang === "hi" ? PRE_TRADE_COPY.title_hi : PRE_TRADE_COPY.title_en;
  const intro = lang === "hi" ? PRE_TRADE_COPY.intro_hi : PRE_TRADE_COPY.intro_en;
  const bullets = lang === "hi" ? PRE_TRADE_COPY.bullets_hi : PRE_TRADE_COPY.bullets_en;
  const cta = lang === "hi" ? PRE_TRADE_COPY.cta_hi : PRE_TRADE_COPY.cta_en;
  const cancel = lang === "hi" ? PRE_TRADE_COPY.cancel_hi : PRE_TRADE_COPY.cancel_en;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="pre-trade-modal-title"
      data-testid="pre-trade-risk-modal"
      data-lang={lang}
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 supports-backdrop-filter:backdrop-blur-sm p-4"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="w-full max-w-md rounded-2xl border border-red-500/30 bg-neutral-900/90 supports-backdrop-filter:backdrop-blur-xl p-6 shadow-2xl shadow-black/60"
      >
        <div className="mb-4 flex items-start gap-3">
          <AlertTriangle
            className="mt-0.5 h-6 w-6 shrink-0 text-red-400"
            aria-hidden="true"
          />
          <h2
            id="pre-trade-modal-title"
            data-testid="pre-trade-modal-title"
            className="text-lg font-bold text-neutral-100"
          >
            {title}
          </h2>
        </div>

        <p
          data-testid="pre-trade-modal-intro"
          className="mb-3 text-sm leading-relaxed text-neutral-300"
        >
          {intro}
        </p>

        <ul
          data-testid="pre-trade-modal-bullets"
          className="mb-6 space-y-1.5 text-xs leading-relaxed text-neutral-300"
        >
          {bullets.map((b, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-red-400" aria-hidden="true" />
              <span>{b}</span>
            </li>
          ))}
        </ul>

        <div className="flex flex-col gap-2 sm:flex-row">
          <Button
            type="button"
            variant="ghost"
            onClick={onCancel}
            data-testid="pre-trade-modal-cancel"
            className="flex-1 text-neutral-300 hover:bg-white/5"
          >
            {cancel}
          </Button>
          <Button
            type="button"
            onClick={() => {
              safeWrite(LS_KEY_PRE_TRADE_ACK, new Date().toISOString());
              onConfirm();
            }}
            data-testid="pre-trade-modal-confirm"
            className="flex-1 bg-red-500 text-white hover:bg-red-400"
          >
            {cta}
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
