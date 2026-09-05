/**
 * The level ladder — pure logic, no React, no network (founder spec 2026-09-05).
 *
 *   Level 1  NAYA         default for every NEW signup
 *   Level 2  SEEKH RAHA   broker connected + first subscription + first signal seen
 *   Level 3  BANANE WALA  + first template cloned + first backtest run
 *   Level 4  PRO          + first strategy built — OR the Settings toggle, any time
 *
 * Existing accounts default to Pro (they know today's UI); founder/admin
 * accounts stay Pro; new signups start at Level 1. Pro is always one toggle
 * away; switching modes never loses data — the earned level is kept.
 *
 * State rides `users.notification_prefs` under reserved `_ui_*` keys (same
 * mechanism the onboarding flow uses for `_onboarding_goal`), so no migration.
 */

export type UiLevel = 1 | 2 | 3 | 4;

/** The customer's explicit choice in Settings. "auto" = follow the ladder. */
export type ModeChoice = "auto" | "simple" | "pro";

/** Facts the ladder is computed from. Each is "has this EVER happened". */
export interface UnlockFacts {
  brokerConnected: boolean;
  hasSubscription: boolean;
  firstSignalSeen: boolean;
  templateCloned: boolean;
  backtestRun: boolean;
  strategyBuilt: boolean;
}

export const EMPTY_FACTS: UnlockFacts = {
  brokerConnected: false,
  hasSubscription: false,
  firstSignalSeen: false,
  templateCloned: false,
  backtestRun: false,
  strategyBuilt: false,
};

/** Persisted shape (inside notification_prefs). All fields optional on read. */
export interface LevelState {
  /** Highest level EARNED so far (never goes down). */
  earned: UiLevel;
  choice: ModeChoice;
  /** ISO timestamps: when each fact first became true / each level unlocked. */
  facts: Partial<Record<keyof UnlockFacts, string>>;
  unlockedAt: Partial<Record<2 | 3 | 4, string>>;
  /** Levels whose unlock has been announced (home card + nudge shown). */
  announced: UiLevel[];
  /** The first-Pro expanded-sidebar nudge has been shown. */
  proNudgeSeen: boolean;
  /** Simple 3-step onboarding done (or skipped). */
  simpleOnboardingDone: boolean;
}

/** Ladder launch: accounts created before this are EXISTING → Pro by default. */
export const LADDER_LAUNCH_AT = "2026-09-05T00:00:00Z";

/** Reserved keys inside notification_prefs. */
export const PREF_KEY = "_ui_ladder";

export const LEVEL_NAME_KEY = {
  1: "level1_name",
  2: "level2_name",
  3: "level3_name",
  4: "level4_name",
} as const;

export function computeEarnedLevel(f: UnlockFacts): UiLevel {
  const l2 = f.brokerConnected && f.hasSubscription && f.firstSignalSeen;
  const l3 = l2 && f.templateCloned && f.backtestRun;
  const l4 = l3 && f.strategyBuilt;
  if (l4) return 4;
  if (l3) return 3;
  if (l2) return 2;
  return 1;
}

/** What the customer actually sees. Pro choice → 4. Simple choice → the
 *  earned level, capped at 3 (Simple never shows the Pro chrome). Auto → earned. */
export function effectiveLevel(earned: UiLevel, choice: ModeChoice): UiLevel {
  if (choice === "pro") return 4;
  if (choice === "simple") return Math.min(earned, 3) as UiLevel;
  return earned;
}

interface UserLike {
  is_admin?: boolean;
  role?: string;
  created_at?: string;
}

/** The default for an account with NO stored ladder state (C11). */
export function defaultLevelFor(user: UserLike): UiLevel {
  if (user.is_admin) return 4;
  if (user.role === "admin" || user.role === "super_admin") return 4;
  if (user.created_at && Date.parse(user.created_at) < Date.parse(LADDER_LAUNCH_AT)) return 4;
  return 1;
}

export function initialState(user: UserLike, now: string): LevelState {
  const lvl = defaultLevelFor(user);
  return {
    earned: lvl,
    choice: "auto",
    facts: {},
    unlockedAt: lvl === 4 ? { 2: now, 3: now, 4: now } : {},
    // An existing/founder account is never "announced" into Pro — it is
    // simply where they already were; and it never sees Simple onboarding.
    announced: lvl === 4 ? [2, 3, 4] : [],
    proNudgeSeen: lvl === 4,
    simpleOnboardingDone: lvl === 4,
  };
}

/** Merge the freshly observed facts; returns the new state + any NEW unlocks. */
export function applyFacts(
  state: LevelState,
  observed: Partial<UnlockFacts>,
  now: string,
): { state: LevelState; newlyUnlocked: UiLevel[] } {
  const facts = { ...state.facts };
  for (const [k, v] of Object.entries(observed) as Array<[keyof UnlockFacts, boolean | undefined]>) {
    if (v && !facts[k]) facts[k] = now;
  }
  const full: UnlockFacts = {
    brokerConnected: !!facts.brokerConnected,
    hasSubscription: !!facts.hasSubscription,
    firstSignalSeen: !!facts.firstSignalSeen,
    templateCloned: !!facts.templateCloned,
    backtestRun: !!facts.backtestRun,
    strategyBuilt: !!facts.strategyBuilt,
  };
  const computed = computeEarnedLevel(full);
  const earned = Math.max(state.earned, computed) as UiLevel;
  const unlockedAt = { ...state.unlockedAt };
  const newlyUnlocked: UiLevel[] = [];
  for (const lvl of [2, 3, 4] as const) {
    if (earned >= lvl && !unlockedAt[lvl]) {
      unlockedAt[lvl] = now;
      newlyUnlocked.push(lvl);
    }
  }
  return { state: { ...state, facts, earned, unlockedAt }, newlyUnlocked };
}

export function markAnnounced(state: LevelState, level: UiLevel): LevelState {
  if (state.announced.includes(level)) return state;
  return { ...state, announced: [...state.announced, level] };
}

/** The next unlock still to be announced, lowest first. */
export function pendingAnnouncement(state: LevelState): UiLevel | null {
  for (const lvl of [2, 3, 4] as const) {
    if (state.earned >= lvl && !state.announced.includes(lvl)) return lvl;
  }
  return null;
}

// ─── Route classification (C9) ─────────────────────────────────────────

/** Minimum level that may open a path. Anything not listed is Pro (4). */
const LEVEL_ROUTES: Array<[RegExp, UiLevel]> = [
  [/^\/$/, 1],
  [/^\/marketplace(\/me)?\/?$/, 1], // pick a strategy · my joined strategies
  [/^\/marketplace\/[^/]+\/?$/, 1], // listing detail + subscribe
  [/^\/showcase(\/|$)/, 1],
  [/^\/brokers(\/|$)/, 1],
  [/^\/signals(\/|$)/, 1],
  [/^\/help(\/|$)/, 1],
  [/^\/support(\/|$)/, 1],
  [/^\/settings(\/|$)/, 1],
  [/^\/pricing(\/|$)/, 1],
  [/^\/onboarding(\/|$)/, 1],
  [/^\/strategies\/templates(\/|$)/, 2],
  [/^\/strategies\/(indicators|import-pine)(\/|$)/, 4], // Indicator Library + Pine import are Pro
  [/^\/strategies\/new(\/|$)/, 3],
  [/^\/strategies\/?$/, 3],
  [/^\/strategies\/[^/]+\/?$/, 3], // a strategy the customer built
  [/^\/indicators\/?$/, 3], // Learn Indicators
];

export function minLevelForPath(pathname: string): UiLevel {
  const path = pathname.split("?")[0].replace(/\/+$/, "") || "/";
  for (const [re, lvl] of LEVEL_ROUTES) if (re.test(path)) return lvl;
  return 4;
}

export function canOpen(level: UiLevel, pathname: string): boolean {
  return level >= minLevelForPath(pathname);
}

/** Tiles shown on the Simple home at a level, in order. */
export type TileId = "strategy" | "broker" | "signals" | "help" | "templates" | "build" | "learn";

export const TILE_ROUTE: Record<TileId, string> = {
  strategy: "/marketplace",
  broker: "/brokers",
  signals: "/signals",
  help: "/help",
  templates: "/strategies/templates",
  build: "/strategies/new/beginner",
  learn: "/indicators",
};

export function tilesForLevel(level: UiLevel): TileId[] {
  const base: TileId[] = ["strategy", "broker", "signals", "help"];
  if (level >= 2) base.push("templates");
  if (level >= 3) base.push("build", "learn");
  return base;
}

/** The level a tile belongs to (for the "just unlocked" celebration). */
export const TILE_LEVEL: Record<TileId, UiLevel> = {
  strategy: 1,
  broker: 1,
  signals: 1,
  help: 1,
  templates: 2,
  build: 3,
  learn: 3,
};
