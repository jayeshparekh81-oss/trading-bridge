/**
 * Per-subscriber marketplace settings — shared types + the even/2-20 sizing
 * validation. Used by the settings UI and its tests.
 *
 * The backend persists these columns only after the fan-out (M4) merge; until
 * then a PATCH validates-but-doesn't-store and returns ``applied: false``
 * (``pending_fanout_merge: true``), and the UI renders a paper-only preview.
 *
 * A new subscription defaults to ``offline`` (MANUAL) — the backend's
 * new-subscription default since migration 040. Execution is still simulated
 * (``is_paper``) until live trading is enabled (Phase 3 / empanelment); the
 * mode chosen here governs HOW signals are taken once live, and MANUAL means
 * the subscriber opts in per signal rather than auto-executing.
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
  "New subscriptions default to Offline / manual — you opt in per signal. Everything is still simulated (paper) until live trading is enabled (Phase 3); the mode you pick governs how signals are taken once live.";

// ── Direction filter (subscribe selector) ─────────────────────────────
// Backend column marketplace_subscriptions.direction_filter — values are
// 'all' | 'long' | 'short' (CHECK-enforced, migration 035). The UI shows
// Long / Short / Both where **Both === 'all'** (there is NO literal 'both').
// NOT yet accepted by the settings PATCH — the picker is PREVIEW-ONLY until the
// backend exposes direction_filter (see subscription-settings.tsx save()).
export const DIRECTION_FILTERS = ["long", "short", "all"] as const;
export type DirectionFilter = (typeof DIRECTION_FILTERS)[number];
export const DIRECTION_LABELS: Record<DirectionFilter, string> = {
  long: "Long",
  short: "Short",
  all: "Both",
};

// ── Vehicle (instrument type) ─────────────────────────────────────────
// The trading vehicle. It is a property of the STRATEGY
// (strategy_json.instrument_type) — the frontend can't see it yet, so the
// picker runs on a PLACEHOLDER until the backend exposes it. Vehicle
// CONSTRAINS direction: Cash is long-only (no shorting cash equity).
export const VEHICLES = ["cash", "futures", "options"] as const;
export type Vehicle = (typeof VEHICLES)[number];
export const VEHICLE_LABELS: Record<Vehicle, string> = {
  cash: "Cash",
  futures: "Futures",
  options: "Options",
};
export const VEHICLE_ALLOWED_DIRECTIONS: Record<Vehicle, readonly DirectionFilter[]> = {
  cash: ["long"], // cash mein short nahi ho sakta
  futures: ["long", "short", "all"],
  options: ["long", "short", "all"],
};

// Even-lots stepper bounds — mirror validateLotsOverride's rule.
export const LOTS_MIN = 2;
export const LOTS_MAX = 20;
export const LOTS_STEP = 2;

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
