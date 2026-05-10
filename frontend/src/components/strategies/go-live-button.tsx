"use client";

/**
 * Go Live button — gated on the SafetyChain pre-flight verdict.
 *
 * Disabled until every blocking check passes; on hover, the disabled
 * state surfaces a Hinglish tooltip telling the user what to fix.
 * Clicking the enabled button opens the parent's `GoLiveModal` via
 * the `onClick` callback — this component intentionally does not own
 * any modal state so the strategy detail page can position the modal
 * wherever it wants.
 */

import { motion } from "framer-motion";
import { Rocket, ShieldOff } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SafetyChainResult } from "./safety-pre-flight-panel";

interface GoLiveButtonProps {
  preflight: SafetyChainResult | null;
  isPreflightLoading: boolean;
  onClick: () => void;
}

export function GoLiveButton({
  preflight,
  isPreflightLoading,
  onClick,
}: GoLiveButtonProps) {
  const allPassed = !!preflight?.all_passed;
  const disabled = !allPassed || isPreflightLoading;

  const blockingMessage = !allPassed
    ? preflight?.blocking_check?.reason_hinglish ??
      "Safety checks pass karo pehle"
    : null;

  const button = (
    <motion.button
      whileHover={!disabled ? { scale: 1.02 } : undefined}
      whileTap={!disabled ? { scale: 0.98 } : undefined}
      disabled={disabled}
      onClick={onClick}
      type="button"
      className={cn(
        "rounded-xl px-6 py-3 text-base font-semibold text-white transition-all duration-300",
        "inline-flex items-center justify-center gap-2",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-purple/40",
        disabled
          ? "bg-white/[0.04] text-muted-foreground cursor-not-allowed border border-white/[0.06]"
          : cn(
              "bg-gradient-to-r from-accent-purple to-pink-500",
              "hover:shadow-[0_0_30px_rgba(168,85,247,0.45)]",
            ),
      )}
    >
      {disabled ? (
        <>
          <ShieldOff className="h-4 w-4" />
          {isPreflightLoading ? "Checks running…" : "Go Live (locked)"}
        </>
      ) : (
        <>
          <Rocket className="h-4 w-4" />
          🚀 Go Live
        </>
      )}
    </motion.button>
  );

  if (!disabled) return button;

  // Disabled buttons don't fire mouse events, so the native
  // ``title`` attribute on the wrapping span is what surfaces the
  // Hinglish hint on hover. Avoids a Provider dependency for one
  // tooltip and works on every browser.
  return (
    <span
      className="inline-block"
      title={blockingMessage ?? undefined}
    >
      {button}
    </span>
  );
}
