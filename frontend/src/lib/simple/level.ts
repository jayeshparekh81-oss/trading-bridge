/**
 * Simple mode — pure logic, no React, no network.
 *
 * Founder's call (2026-09-05, evening): NO LOCKS. Nothing is gated at any
 * level; simplicity comes from ORDER and plain words. What remains of the
 * "ladder" is guidance only:
 *
 *   - the journey line ("Aapka safar: 1 / 4 kadam · Agla: Broker jodo"),
 *     computed from facts the customer has actually established;
 *   - the mode: Simple (no sidebar, four big tiles + "Aur seekhein") or Pro
 *     (the full menu). Existing and founder accounts default to Pro, new
 *     signups to Simple; the Settings toggle / the Pro tile / the Pro card
 *     switch any time and nothing is ever lost.
 *
 * State rides `users.notification_prefs` under the reserved `_ui_ladder` key
 * (the same mechanism onboarding uses), so no migration.
 */

/** 1–3 = guidance steps shown in Simple; 4 = the Pro chrome. */
export type UiLevel = 1 | 2 | 3 | 4;

/** The customer's explicit choice in Settings. "auto" = the account default. */
export type ModeChoice = "auto" | "simple" | "pro";

/** Facts the journey line is computed from. Each is "has this EVER happened". */
export interface JourneyFacts {
  brokerConnected: boolean;
  hasSubscription: boolean;
  firstSignalSeen: boolean;
  templateCloned: boolean;
  backtestRun: boolean;
  strategyBuilt: boolean;
}

export const EMPTY_FACTS: JourneyFacts = {
  brokerConnected: false,
  hasSubscription: false,
  firstSignalSeen: false,
  templateCloned: false,
  backtestRun: false,
  strategyBuilt: false,
};

/** Persisted shape (inside notification_prefs). All fields optional on read. */
export interface LevelState {
  /** The account default: 4 = Pro by default (existing / founder), else 1. */
  earned: UiLevel;
  choice: ModeChoice;
  /** ISO timestamps: when each fact first became true. */
  facts: Partial<Record<keyof JourneyFacts, string>>;
  /** The first-Pro expanded-sidebar nudge has been shown. */
  proNudgeSeen: boolean;
  /** The first Simple-home AlgoMitra nudge has been shown. */
  homeNudgeSeen?: boolean;
  /** Simple 3-step onboarding done (or skipped). */
  simpleOnboardingDone: boolean;
  /** "Aur seekhein" tiles whose one-line AlgoMitra explanation has been shown. */
  tipsShown?: string[];
}

/** Launch: accounts created before this are EXISTING → Pro by default. */
export const LADDER_LAUNCH_AT = "2026-09-05T00:00:00Z";

/** Reserved key inside notification_prefs. */
export const PREF_KEY = "_ui_ladder";

/** The guidance step the facts put the customer on (1–4). Never a gate. */
export function computeEarnedLevel(f: JourneyFacts): UiLevel {
  const l2 = f.brokerConnected && f.hasSubscription && f.firstSignalSeen;
  const l3 = l2 && f.templateCloned && f.backtestRun;
  const l4 = l3 && f.strategyBuilt;
  if (l4) return 4;
  if (l3) return 3;
  if (l2) return 2;
  return 1;
}

/** What the customer sees. Pro choice → 4 (Pro chrome). Simple choice, or the
 *  default for a new signup → the journey step from facts, capped at 3 (Simple
 *  chrome). A Pro-default account in "auto" → 4. Nothing ever switches the
 *  chrome to Pro on its own; only the customer does. */
export function effectiveLevel(earned: UiLevel, choice: ModeChoice, facts?: JourneyFacts): UiLevel {
  if (choice === "pro") return 4;
  if (choice === "auto" && earned === 4) return 4;
  const step = facts ? computeEarnedLevel(facts) : 1;
  return Math.min(step, 3) as UiLevel;
}

/** The stored fact timestamps as booleans. */
export function factFlags(facts: Partial<Record<keyof JourneyFacts, string>> | undefined): JourneyFacts {
  const f = { ...EMPTY_FACTS };
  for (const k of Object.keys(f) as (keyof JourneyFacts)[]) f[k] = !!facts?.[k];
  return f;
}

/** One step of the journey, in plain words (copy key `req_<key>`). */
export type ReqKey = "broker" | "subscribe" | "signal" | "template" | "backtest" | "build";

/** What each guidance step is made of, in the order the customer meets them. */
export const REQUIREMENTS: Record<2 | 3 | 4, { key: ReqKey; fact: keyof JourneyFacts }[]> = {
  2: [
    { key: "broker", fact: "brokerConnected" },
    { key: "subscribe", fact: "hasSubscription" },
    { key: "signal", fact: "firstSignalSeen" },
  ],
  3: [
    { key: "template", fact: "templateCloned" },
    { key: "backtest", fact: "backtestRun" },
  ],
  4: [{ key: "build", fact: "strategyBuilt" }],
};

/** Steps of `level` the customer has NOT done yet (empty = done). */
export function remainingFor(level: 2 | 3 | 4, facts: JourneyFacts): ReqKey[] {
  return REQUIREMENTS[level].filter((r) => !facts[r.fact]).map((r) => r.key);
}

/** "Aapka safar: 1 / 4 kadam" + the very next thing to do. Guidance only. */
export function progressFor(level: UiLevel, facts: JourneyFacts): { done: UiLevel; total: 4; next: ReqKey | null } {
  if (level >= 4) return { done: 4, total: 4, next: null };
  const nextLevel = (level + 1) as 2 | 3 | 4;
  const remaining = remainingFor(nextLevel, facts);
  return { done: level, total: 4, next: remaining[0] ?? REQUIREMENTS[nextLevel][0].key };
}

interface UserLike {
  is_admin?: boolean;
  role?: string;
  created_at?: string;
}

/** The default for an account with NO stored state: existing/founder → Pro, new → Simple. */
export function defaultLevelFor(user: UserLike): UiLevel {
  if (user.is_admin) return 4;
  if (user.role === "admin" || user.role === "super_admin") return 4;
  if (user.created_at && Date.parse(user.created_at) < Date.parse(LADDER_LAUNCH_AT)) return 4;
  return 1;
}

export function initialState(user: UserLike): LevelState {
  const lvl = defaultLevelFor(user);
  return {
    earned: lvl,
    choice: "auto",
    facts: {},
    // An existing/founder account never sees the Simple onboarding or the
    // first-Pro nudge — Pro is simply where they already were.
    proNudgeSeen: lvl === 4,
    simpleOnboardingDone: lvl === 4,
    tipsShown: [],
  };
}

/** Record freshly observed facts (monotonic — a fact is never un-learned). */
export function applyFacts(state: LevelState, observed: Partial<JourneyFacts>, now: string): LevelState {
  const facts = { ...state.facts };
  let changed = false;
  for (const [k, v] of Object.entries(observed) as Array<[keyof JourneyFacts, boolean | undefined]>) {
    if (v && !facts[k]) {
      facts[k] = now;
      changed = true;
    }
  }
  return changed ? { ...state, facts } : state;
}

// ── Tiles ────────────────────────────────────────────────────────────

/** The four things a new customer does, in order, plus "Aur seekhein". */
export type TileId = "strategy" | "broker" | "signals" | "help" | "templates" | "build";

/** Always these four, always in this order, always open. */
export const MAIN_TILES: TileId[] = ["strategy", "broker", "signals", "help"];

/** "Aur seekhein" — open from day one; a suggestion of order, never a block. */
export type LearnTileId = "templates" | "build" | "pro";
export const LEARN_TILES: LearnTileId[] = ["templates", "build", "pro"];

export const TILE_ROUTE: Record<TileId, string> = {
  strategy: "/marketplace",
  broker: "/brokers",
  signals: "/signals",
  help: "/help",
  templates: "/strategies/templates",
  build: "/strategies/new/beginner",
};

/** Copy key of each tile's title (components/simple/*, fixtures, tests). */
export const TILE_TITLE_KEY: Record<TileId, string> = {
  strategy: "tile_strategy",
  broker: "tile_broker",
  signals: "tile_signals",
  help: "tile_help",
  templates: "tile_templates",
  build: "tile_build",
};
