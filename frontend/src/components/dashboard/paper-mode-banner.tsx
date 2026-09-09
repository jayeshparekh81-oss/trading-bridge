"use client";

import { FlaskConical, Layers } from "lucide-react";

import { LIVE_WORD, PAPER_WORD, type PaperScope } from "@/lib/paper-mode";
import { cn } from "@/shared/lib/utils";

/**
 * The "orders are simulated" disclosure — and the per-row label that replaces
 * it wherever one sentence cannot be true.
 *
 * ⚠️ `scope` IS REQUIRED, DELIBERATELY. This banner used to compute its own
 * truth from the GLOBAL `paper_mode` flag, and was mounted over the founder's
 * REAL-MONEY positions, telling him "broker ko koi asli order nahi jaata"
 * while Dhan held a live BSE futures position. Requiring the caller to hand
 * in a scope means no surface can ever again disclose a mode it did not
 * actually read for the rows it is actually showing. See `@/lib/paper-mode`
 * for the resolution rule and why the global flag is only a fallback.
 *
 * A banner is a claim about EVERY row beneath it, so it renders only when
 * every row in scope is simulated. On a mixed surface it steps aside and
 * points at the per-row labels instead of averaging two different truths
 * into one false sentence.
 */
export function PaperModeBanner({
  scope,
  className,
}: {
  scope: PaperScope;
  className?: string;
}) {
  // Unknown — we have not read the mode, so we name neither. Real money is
  // never disclosed as simulated on the strength of a failed fetch.
  if (scope === "unknown") return null;
  // Nothing here is simulated: there is no disclosure to make.
  if (scope === "none-paper") return null;

  if (scope === "mixed") {
    return (
      <div
        role="status"
        aria-live="polite"
        data-testid="paper-mode-banner-mixed"
        className={cn(
          "flex items-start gap-2 rounded-lg border border-accent-gold/30",
          "bg-accent-gold/10 px-4 py-2.5 text-13 text-accent-gold",
          className,
        )}
      >
        <Layers className="h-4 w-4 shrink-0 mt-0.5" aria-hidden="true" />
        <p className="leading-relaxed">
          <span className="font-semibold uppercase">Paper aur live dono</span>{" "}
          — is list mein dono tarah ki rows hain. Har row ka apna mode uske
          saath likha hai; neeche{" "}
          <span className="font-semibold">{LIVE_WORD}</span> matlab asli paisa.
        </p>
      </div>
    );
  }

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

/**
 * The per-row mode label, for surfaces that mix simulated and real rows.
 *
 * `null` renders NOTHING: a row whose mode we have not read is not labelled
 * live, and is not labelled paper. Same discipline as the banner — the
 * absence of a label is honest, a wrong label is not.
 *
 * Colours match the badges the /strategies list already prints for the same
 * fact, so one mode never wears two liveries across two screens.
 */
export function PaperRowBadge({
  paper,
  className,
}: {
  paper: boolean | null;
  className?: string;
}) {
  if (paper === null) return null;

  return (
    <span
      data-testid={paper ? "row-mode-paper" : "row-mode-live"}
      title={
        paper
          ? "Simulated — no order reaches the broker"
          : "Real money — orders reach the broker"
      }
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5",
        "text-10 font-medium uppercase tracking-wide",
        paper
          ? "bg-muted text-muted-foreground border-border"
          : "bg-loss/15 text-loss border-loss/30",
        className,
      )}
    >
      {paper ? PAPER_WORD : `● ${LIVE_WORD}`}
    </span>
  );
}
