"use client";

/**
 * First time Pro opens: the sidebar is shown EXPANDED once and AlgoMitra says
 * where the toggle is — so the collapsed state is never a mystery. Shown once
 * per account (ladder.proNudgeSeen), dismissed by the customer.
 */

import { useEffect, useState } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { Sparkles, X } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";
import { useLadder } from "@/hooks/useLadder";
import { t } from "@/lib/simple/copy";

/** The sidebar listens for this to expand itself once. */
export const SIDEBAR_EXPAND_EVENT = "tradetri:sidebar-expand";

export function ProWelcomeNudge() {
  const ladder = useLadder();
  const { lang } = useLanguage();
  const reduce = useReducedMotion();
  const show = ladder.ready && ladder.level === 4 && ladder.state !== null && !ladder.state.proNudgeSeen;
  // Local dismissal hides it immediately; the ladder flag hides it for good.
  const [dismissed, setDismissed] = useState(false);
  const open = show && !dismissed;

  // The one side effect: ask the sidebar to show itself EXPANDED this once.
  useEffect(() => {
    if (open) window.dispatchEvent(new CustomEvent(SIDEBAR_EXPAND_EVENT));
  }, [open]);

  function dismiss() {
    setDismissed(true);
    ladder.markProNudgeSeen();
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={reduce ? false : { opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          role="status"
          data-testid="pro-welcome-nudge"
          className="fixed left-3 bottom-24 md:left-[256px] md:bottom-6 z-40 max-w-xs rounded-2xl border border-profit/40 bg-[#0F1629] p-4 shadow-[0_0_28px_rgba(0,255,136,0.18)]"
        >
          <div className="flex items-start gap-3">
            <Sparkles className="h-5 w-5 text-profit shrink-0 mt-0.5" aria-hidden="true" />
            <div className="min-w-0">
              <p className="text-[11px] uppercase tracking-[0.18em] text-profit font-mono">{t(lang, "nudge_prefix")}</p>
              <p className="mt-1 text-sm text-foreground">{t(lang, "nudge_pro_sidebar")}</p>
            </div>
            <button
              type="button"
              onClick={dismiss}
              aria-label="close"
              data-testid="pro-welcome-nudge-close"
              className="ml-1 rounded-full p-1 text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
