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
  /** Lower-snake-case instance id used inside conditions. */
  id: string;
  /** Registry type id — must exist in the Phase 5 indicator registry. */
  type: "ema" | "rsi";
  params: { period: number; source: "close" };
  /** Human-friendly label rendered in step 2/3. */
  label: string;
}

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
      params: { ...ind.params },
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
