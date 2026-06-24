/**
 * Per-subscriber marketplace settings — shared types + the even/2-20 sizing
 * validation. Used by the settings UI and its tests.
 *
 * The backend persists these columns only after the fan-out (M4) merge; until
 * then a PATCH validates-but-doesn't-store and returns ``applied: false``
 * (``pending_fanout_merge: true``), and the UI renders a paper-only preview.
 *
 * Execution is PAPER until live trading is enabled (Phase 3 / empanelment), so
 * ``paper`` is the default and the only mode that runs today.
 */

export const EXECUTION_MODES = ["paper", "auto", "one_click", "offline"] as const;
export type ExecutionMode = (typeof EXECUTION_MODES)[number];

export const EXECUTION_MODE_LABELS: Record<ExecutionMode, string> = {
  paper: "Paper (simulated — no real orders)",
  auto: "Auto (fully automated)",
  one_click: "One-click confirm",
  offline: "Offline / manual",
};

export const EXECUTION_MODE_HELP =
  "Only Paper runs today. Auto / one-click / offline activate when live trading is enabled (Phase 3).";

export interface SubscriptionSettings {
  subscription_id: string;
  lots_override: number | null;
  execution_mode: ExecutionMode;
  is_paper: boolean;
  /** True once the backend actually persisted the values (post fan-out merge). */
  applied: boolean;
  /** True on this branch — the execution columns merge in from feat/marketplace-fanout. */
  pending_fanout_merge: boolean;
}

/** Sizing rule: even integer, 2-20 (4/6/8 …). ``null`` = use the listing default.
 *  Returns an error string for the UI, or ``null`` when valid. */
export function validateLotsOverride(
  value: number | null | undefined,
): string | null {
  if (value == null || Number.isNaN(value)) return null;
  if (!Number.isInteger(value)) return "Lots must be a whole number.";
  if (value < 2) return "Minimum size is 2 lots.";
  if (value > 20) return "Maximum size is 20 lots.";
  if (value % 2 !== 0) return "Lots must be an even number (2, 4, 6 …).";
  return null;
}
