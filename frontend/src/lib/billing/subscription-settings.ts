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
  paper: "Seekhne wala mode (paper) — nakli order, asli paisa nahi",
  auto: "Apne aap (auto) — har signal par order khud jaayega",
  one_click: "Ek tap se (one-click) — har signal par aap ek tap se haan bologe",
  offline: "Haath se (manual) — har signal par faisla aapka",
};

export const EXECUTION_MODE_HELP =
  "Pehle se chuna hua: \"Haath se (manual)\" — har signal par faisla aapka. Abhi sab kuch seekhne wale mode (paper) me chalta hai, koi asli order nahi jaata; asli trading chalu hone par yahan chuna tareeka lagega.";

// ── Direction filter (subscribe selector) ─────────────────────────────
// Backend column marketplace_subscriptions.direction_filter — values are
// 'all' | 'long' | 'short' (CHECK-enforced, migration 035). The UI shows
// Long / Short / Both where **Both === 'all'** (there is NO literal 'both').
// NOT yet accepted by the settings PATCH — the picker is PREVIEW-ONLY until the
// backend exposes direction_filter (see subscription-settings.tsx save()).
export const DIRECTION_FILTERS = ["long", "short", "all"] as const;
export type DirectionFilter = (typeof DIRECTION_FILTERS)[number];
export const DIRECTION_LABELS: Record<DirectionFilter, string> = {
  long: "Sirf kharid (long)",
  short: "Sirf bech (short)",
  all: "Dono",
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
/**
 * How a strategy's DECLARED instrument type is shown. It is a FACT read from
 * strategy_json.instrument_type — never a customer choice. The Vehicle picker
 * stays DISABLED: the platform cannot honestly execute a futures signal as cash
 * or options (wrong price basis, no share sizing, cash cannot short, and every
 * certified number we publish is futures-basis).
 */
export const INSTRUMENT_FACT: Record<Vehicle, string> = {
  cash: "This strategy trades CASH",
  futures: "This strategy trades FUTURES",
  options: "This strategy trades OPTIONS",
};

export function instrumentFact(value: string | null | undefined): string | null {
  if (!value) return null;
  const key = value.trim().toLowerCase() as Vehicle;
  return key in INSTRUMENT_FACT ? INSTRUMENT_FACT[key] : null;
}

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
  /** Which SIDES this subscriber takes. Persisted by the settings PATCH and
   *  enforced at the fan-out entry gate; exits are never filtered. */
  direction_filter: DirectionFilter;
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
  if (!Number.isInteger(value)) return "Poora number likho — 2, 4, 6… (whole number).";
  if (value < 2) return "Kam se kam 2 rakho (minimum 2).";
  if (value > 20) return "Zyada se zyada 20 rakho (maximum 20).";
  if (value % 2 !== 0) return "Jodi wala number rakho — 2, 4, 6… (even number).";
  return null;
}
