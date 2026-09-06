"use client";

import { FlaskConical } from "lucide-react";

import { useSystemMode } from "@/hooks/useSystemMode";
import { cn } from "@/shared/lib/utils";

/**
 * PaperModeBanner — the "orders are simulated" strip, mounted on every
 * surface where a customer can ACT (signals, My Strategies, positions,
 * the Deploy panel).
 *
 * ONE owner of the fact. The banner used to re-implement the whole
 * ``GET /api/system/mode`` fetch — its own BASE fallback, its own poll,
 * its own parse — beside ``useSystemMode``, which does exactly that.
 * Two copies of one fact can disagree; now the hook is the only reader
 * and this component only renders what the hook read.
 *
 * Three server states, three behaviours:
 *   paper_mode === true   → the strip, saying orders are simulated
 *   paper_mode === false  → nothing (there is nothing to disclose)
 *   unknown (hook null)   → NOTHING. First poll still in flight, or every
 *                           poll failed. We have not read the flag, so we
 *                           claim neither simulated nor real.
 *
 * Nothing here is hardcoded: the copy is behind the server's own boolean,
 * so a platform flipped to real money stops saying "simulated" on its own.
 */
export function PaperModeBanner({ className }: { className?: string }) {
  const mode = useSystemMode();

  // Unknown — assert nothing either way.
  if (mode === null) return null;
  if (!mode.paper_mode) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="paper-mode-banner"
      data-tour-id="paper-mode-banner"
      className={cn(
        "flex items-start gap-2 rounded-lg border border-accent-gold/30",
        "bg-accent-gold/10 px-4 py-2.5 text-13 text-accent-gold",
        className,
      )}
    >
      <FlaskConical className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
      <p className="leading-relaxed">
        <span className="font-semibold uppercase">Paper mode</span> — order
        sirf simulate hote hain, broker ko koi asli order nahi jaata.
      </p>
    </div>
  );
}
