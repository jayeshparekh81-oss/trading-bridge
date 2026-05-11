/**
 * Beginner-builder presets — goal → indicator + entry recipe.
 *
 * The Phase 1 StrategyJSON schema validates the payload at the backend
 * boundary; the shapes here mirror the camelCase aliases the schema
 * serialises to, so the wizard can hand the value straight to
 * ``POST /api/strategies`` without an extra mapper.
 *
 * Indicator ids (``ema_9``, ``rsi_14``, ...) must be lower-snake-case
 * per ``IndicatorConfig`` validation, and every id referenced in entry
 * conditions must appear in ``indicators[*].id``.
 */
export type BeginnerGoal = "intraday" | "swing" | "scalping" | "safe";

export interface GoalCard {
  id: BeginnerGoal;
  title: string;
  blurb: string;
  hinglish: string;
  badge: string;
}

export const GOAL_CARDS: GoalCard[] = [
  {
    id: "intraday",
    title: "Intraday",
    blurb: "Same-day trades. Square off before market close.",
    hinglish: "Din ke andar trade kholo aur band karo. Overnight risk nahi.",
    badge: "Day trader",
  },
  {
    id: "swing",
    title: "Swing",
    blurb: "Hold a few days. Catch larger moves with wider stops.",
    hinglish: "2-5 din tak position rakho. Bade move pakdo, thoda patience chahiye.",
    badge: "Multi-day",
  },
  {
    id: "scalping",
    title: "Scalping",
    blurb: "Tiny, fast moves. Many trades, tight stops.",
    hinglish: "Chhote-chhote moves. Bahut sare trades, tight stop loss.",
    badge: "High frequency",
  },
  {
    id: "safe",
    title: "Safe Learning Mode",
    blurb: "Gentle rules. Designed to teach, not to maximise PnL.",
    hinglish: "Sikhne ke liye banaya. Risk kam, samajhna asaan.",
    badge: "Learner-friendly",
  },
];

export interface IndicatorPreset {
  /** Lower-snake-case instance id used inside conditions. The id is
   *  the stable handle for ``trendCompare`` / ``rsiId`` references —
   *  it intentionally encodes the *default* period (``ema_9``,
   *  ``rsi_14``) for readability, but the user can override the
   *  actual period via ``periodOverrides`` without renaming the id.
   *  Renaming would risk breaking saved entry conditions that
   *  reference these ids by string. */
  id: string;
  /** Registry type id — must exist in the Phase 5 indicator registry. */
  type: "ema" | "rsi";
  params: { period: number; source: "close" };
  /** Default human-friendly label rendered in step 2/3. ``presetLabel``
   *  below derives the runtime label from this default + any
   *  override the user typed (e.g., "EMA-9" → "EMA-13"). */
  label: string;
}


/**
 * Per-instance period override map keyed by the indicator's stable id
 * (``ema_9`` → 13, ``rsi_14`` → 21, …). An entry's *absence* means
 * "use the preset default" — an empty object is the no-override state.
 *
 * Stored as strings (not numbers) so the UI input layer can carry
 * intermediate states ("", "0", "abc") through the reducer without
 * coercion loss; validation + numeric coercion happen at the boundary
 * in :func:`validatePeriodOverrides` and :func:`buildStrategyJson`.
 */
export type PeriodOverrides = Record<string, string>;

/** UI / backend agreement: integers in [1, 1000]. The backend's
 *  ``IndicatorConfig`` accepts any positive int, so 1000 is a UI cap
 *  chosen to keep beginner backtests tractable, not a schema rule. */
export const PERIOD_MIN = 1;
export const PERIOD_MAX = 1000;

export interface GoalPreset {
  goal: BeginnerGoal;
  indicators: IndicatorPreset[];
  /**
   * Entry rule expressed in plain language for the preview card.
   * The actual DSL is built by ``buildStrategyJson`` below.
   */
  entryHinglish: string;
  /**
   * Names of the two ids that should be compared with ``>``.
   * For "safe" only RSI < 30 is used and ``trendCompare`` is null.
   */
  trendCompare: { fast: string; slow: string } | null;
  /** Indicator id to use for RSI < 30 condition. */
  rsiId: string;
  defaultStopLossPercent: number;
  defaultTargetPercent: number;
}

export const GOAL_PRESETS: Record<BeginnerGoal, GoalPreset> = {
  intraday: {
    goal: "intraday",
    indicators: [
      { id: "ema_9", type: "ema", params: { period: 9, source: "close" }, label: "EMA-9 (fast trend)" },
      { id: "ema_21", type: "ema", params: { period: 21, source: "close" }, label: "EMA-21 (slow trend)" },
      { id: "rsi_14", type: "rsi", params: { period: 14, source: "close" }, label: "RSI-14 (momentum)" },
    ],
    entryHinglish:
      "Jab EMA-9 EMA-21 ke upar ho (uptrend) aur RSI-14 oversold zone (<30) mein aaye, BUY karo.",
    trendCompare: { fast: "ema_9", slow: "ema_21" },
    rsiId: "rsi_14",
    defaultStopLossPercent: 1,
    defaultTargetPercent: 2,
  },
  swing: {
    goal: "swing",
    indicators: [
      { id: "ema_20", type: "ema", params: { period: 20, source: "close" }, label: "EMA-20 (fast trend)" },
      { id: "ema_50", type: "ema", params: { period: 50, source: "close" }, label: "EMA-50 (slow trend)" },
      { id: "rsi_14", type: "rsi", params: { period: 14, source: "close" }, label: "RSI-14 (momentum)" },
    ],
    entryHinglish:
      "Jab EMA-20 EMA-50 ke upar ho (longer uptrend) aur RSI-14 < 30 ho, BUY karo.",
    trendCompare: { fast: "ema_20", slow: "ema_50" },
    rsiId: "rsi_14",
    defaultStopLossPercent: 2,
    defaultTargetPercent: 4,
  },
  scalping: {
    goal: "scalping",
    indicators: [
      { id: "ema_5", type: "ema", params: { period: 5, source: "close" }, label: "EMA-5 (super fast)" },
      { id: "ema_9", type: "ema", params: { period: 9, source: "close" }, label: "EMA-9 (fast)" },
      { id: "rsi_7", type: "rsi", params: { period: 7, source: "close" }, label: "RSI-7 (fast momentum)" },
    ],
    entryHinglish:
      "Jab EMA-5 EMA-9 ke upar ho aur RSI-7 < 30 ho, BUY karo. Tight stop loss rakho.",
    trendCompare: { fast: "ema_5", slow: "ema_9" },
    rsiId: "rsi_7",
    defaultStopLossPercent: 0.5,
    defaultTargetPercent: 1,
  },
  safe: {
    goal: "safe",
    indicators: [
      { id: "ema_20", type: "ema", params: { period: 20, source: "close" }, label: "EMA-20 (trend)" },
      { id: "rsi_14", type: "rsi", params: { period: 14, source: "close" }, label: "RSI-14 (momentum)" },
    ],
    entryHinglish:
      "Jab RSI-14 oversold zone (<30) mein aaye, BUY karo. Sikhne ke liye sabse simple rule.",
    trendCompare: null,
    rsiId: "rsi_14",
    defaultStopLossPercent: 1,
    defaultTargetPercent: 2,
  },
};

// ─── StrategyJSON builder ──────────────────────────────────────────────

interface IndicatorConditionDsl {
  type: "indicator";
  left: string;
  op: ">" | "<";
  right?: string;
  value?: number;
}

export interface StrategyJsonPayload {
  id: string;
  name: string;
  mode: "beginner";
  version: 1;
  indicators: { id: string; type: string; params: Record<string, unknown> }[];
  entry: {
    side: "BUY";
    operator: "AND";
    conditions: IndicatorConditionDsl[];
  };
  exit: {
    targetPercent: number;
    stopLossPercent: number;
  };
  execution: {
    mode: "backtest";
    orderType: "MARKET";
    productType: "INTRADAY";
  };
}

export interface BuildStrategyArgs {
  id: string;
  name: string;
  goal: BeginnerGoal;
  stopLossPercent: number;
  targetPercent: number;
  /** Optional per-indicator period overrides. ``validatePeriodOverrides``
   *  must have returned ``null`` before this is consumed — the
   *  builder assumes every present override is a valid int in range. */
  periodOverrides?: PeriodOverrides;
}

export function buildStrategyJson(args: BuildStrategyArgs): StrategyJsonPayload {
  const preset = GOAL_PRESETS[args.goal];
  const conditions: IndicatorConditionDsl[] = [];

  if (preset.trendCompare) {
    conditions.push({
      type: "indicator",
      left: preset.trendCompare.fast,
      op: ">",
      right: preset.trendCompare.slow,
    });
  }
  conditions.push({
    type: "indicator",
    left: preset.rsiId,
    op: "<",
    value: 30,
  });

  return {
    id: args.id,
    name: args.name,
    mode: "beginner",
    version: 1,
    indicators: preset.indicators.map((ind) => ({
      id: ind.id,
      type: ind.type,
      params: {
        ...ind.params,
        period: resolvePeriod(ind, args.periodOverrides),
      },
    })),
    entry: { side: "BUY", operator: "AND", conditions },
    exit: {
      targetPercent: args.targetPercent,
      stopLossPercent: args.stopLossPercent,
    },
    execution: {
      mode: "backtest",
      orderType: "MARKET",
      productType: "INTRADAY",
    },
  };
}


/** Resolve the effective period for an indicator: user override
 *  (already validated upstream) wins over the preset default. */
function resolvePeriod(
  ind: IndicatorPreset,
  overrides: PeriodOverrides | undefined,
): number {
  const raw = overrides?.[ind.id];
  if (raw === undefined || raw === "") return ind.params.period;
  const parsed = parsePeriodInput(raw);
  return parsed ?? ind.params.period;
}


/** Parse a user-entered period string into the canonical int form.
 *  Returns ``null`` for any invalid input (empty, non-numeric, out
 *  of range) — callers decide between "fall back to default" and
 *  "block submission". Decimals are floored, matching the
 *  "round down" rule in the spec.
 */
export function parsePeriodInput(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === "") return null;
  const num = Number(trimmed);
  if (!Number.isFinite(num)) return null;
  const floored = Math.floor(num);
  if (floored < PERIOD_MIN || floored > PERIOD_MAX) return null;
  return floored;
}


/** Build the display label for one indicator instance under the
 *  current override set (``EMA-9`` → ``EMA-13`` when 13 is the
 *  override). Falls back to the preset's static label when the
 *  override is absent or invalid so the badge never goes blank
 *  mid-typing. */
export function indicatorDisplayLabel(
  ind: IndicatorPreset,
  overrides: PeriodOverrides | undefined,
): string {
  const raw = overrides?.[ind.id];
  if (raw === undefined || raw.trim() === "") return ind.label;
  const parsed = parsePeriodInput(raw);
  if (parsed === null) return ind.label;
  if (parsed === ind.params.period) return ind.label;
  // Preset labels look like "EMA-9 (fast trend)" — splice the new
  // period into the leading token so the parenthetical qualifier
  // (the role descriptor) stays intact.
  return ind.label.replace(
    /^([A-Za-z]+)-\d+/,
    `$1-${parsed}`,
  );
}


/** Per-id error message for the period override, or ``null`` when
 *  the override is acceptable (either present-and-valid, or absent
 *  → falls back to default). The empty-string state surfaces as a
 *  "Required" message because the user has explicitly cleared the
 *  field; the absence of the key in the map means "untouched, use
 *  default" and passes silently. */
export function validatePeriodOverride(raw: string | undefined): string | null {
  if (raw === undefined) return null;
  const trimmed = raw.trim();
  if (trimmed === "") return "Required.";
  const num = Number(trimmed);
  if (!Number.isFinite(num)) return `Period must be ${PERIOD_MIN}-${PERIOD_MAX}.`;
  const floored = Math.floor(num);
  if (floored < PERIOD_MIN || floored > PERIOD_MAX) {
    return `Period must be ${PERIOD_MIN}-${PERIOD_MAX}.`;
  }
  return null;
}


/** Whole-form check: returns the first error message, or ``null`` if
 *  every override is acceptable. Used by the wizard to block "Next"
 *  on step 2 when any field is invalid. */
export function validatePeriodOverrides(
  goal: BeginnerGoal,
  overrides: PeriodOverrides,
): string | null {
  const preset = GOAL_PRESETS[goal];
  for (const ind of preset.indicators) {
    const err = validatePeriodOverride(overrides[ind.id]);
    if (err) return `${ind.label}: ${err}`;
  }
  return null;
}

// ─── Light-weight client-side validator ────────────────────────────────
//
// Mirrors the structural checks the backend enforces (Pydantic), so we
// can short-circuit obvious mistakes (empty name, bad SL/target) without
// hitting the network. Backend remains the source of truth.

export function validateBuildArgs(args: BuildStrategyArgs): string | null {
  if (!args.name.trim()) return "Strategy ka naam zaroori hai.";
  if (args.name.length > 256) return "Naam 256 characters se chhota rakho.";
  if (!(args.stopLossPercent > 0)) return "Stop Loss % zero se zyada hona chahiye.";
  if (!(args.targetPercent > 0)) return "Target % zero se zyada hona chahiye.";
  if (args.targetPercent <= args.stopLossPercent) {
    return "Target Stop Loss se bada hona chahiye (risk-reward).";
  }
  return null;
}

export function defaultStrategyName(goal: BeginnerGoal): string {
  switch (goal) {
    case "intraday":
      return "My Intraday EMA Crossover";
    case "swing":
      return "My Swing EMA Trend";
    case "scalping":
      return "My Fast Scalper";
    case "safe":
      return "My Safe Learning Strategy";
  }
}
