"use client";

import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface ReactionToastProps {
  message: string | null;
  /** Anchor position. ``"raised"`` lifts the toast above the chat widget when it's open. */
  raised?: boolean;
  onDismiss: () => void;
}

/**
 * Slide-in reaction toast — shown bottom-right, above the AlgoMitra
 * chat button. Auto-dismiss is owned by the parent hook so it can
 * also clear on route change / unmount.
 */
export function ReactionToast({ message, raised = false, onDismiss }: ReactionToastProps) {
  return (
    <AnimatePresence>
      {message && (
        <motion.div
          key={message}
          initial={{ opacity: 0, y: 12, x: 20 }}
          animate={{ opacity: 1, y: 0, x: 0 }}
          exit={{ opacity: 0, y: 8, x: 20 }}
          transition={{ duration: 0.25 }}
          role="status"
          aria-live="polite"
          className={cn(
            "fixed z-50 right-4 md:right-6 max-w-[calc(100%-2rem)] md:max-w-sm",
            // Stack above the floating chat launcher (bottom-20 mobile / bottom-6 md+).
            // Raised when chat panel is open so it doesn't collide with the panel header.
            raised
              ? "bottom-[640px] md:bottom-[640px]"
              : "bottom-32 md:bottom-20",
          )}
        >
          <div className="pointer-events-auto flex items-start gap-3 rounded-2xl border border-accent-gold/30 bg-card/95 backdrop-blur px-4 py-3 shadow-lg shadow-accent-gold/10">
            <div className="text-[10px] uppercase tracking-wide text-accent-gold font-semibold mt-0.5 shrink-0">
              AlgoMitra
            </div>
            <div className="flex-1 text-sm leading-relaxed text-foreground whitespace-pre-wrap break-words">
              {message}
            </div>
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Dismiss"
              className="shrink-0 rounded-md p-1 -mr-1 -mt-1 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
