/**
 * Intermediate-builder shared types + StrategyJSON serializer.
 *
 * The frontend mirrors the Phase 1 ``StrategyJSON`` schema using the
 * camelCase aliases the backend writes (``targetPercent``, ``orderType``,
 * etc). Pydantic's ``populate_by_name`` accepts both forms so this still
 * round-trips, but matching the alias keeps the wire form stable with
 * what ``GET /api/strategies`` returns later.
 *
 * Validation here mirrors the Pydantic constraints we can check
 * client-side (range, exclusivity). The backend remains the source of
 * truth — this layer just lets the UI fail fast with friendly copy
 * before a network round-trip.
 */
import type { IndicatorMetadata } from "@/components/strategies/indicator-library";

// ─── Indicator instance ────────────────────────────────────────────────

export interface SelectedIndicator {
  /** Lower-snake-case instance id used inside conditions (e.g. ``ema_20``). */
  id: string;
  /** Registry type id (``ema``, ``rsi``, ...). Drives calculation_function. */
  type: string;
  /** Display label assembled from name + key params. */
  label: string;
  /** User-supplied parameters (name → value). */
  params: Record<string, number | string>;
  /** Catalogue metadata snapshot, kept for label/inputs lookups. */
  meta: IndicatorMetadata;
}

// ─── Conditions ────────────────────────────────────────────────────────

export type ConditionOp = ">" | "<" | ">=" | "<=" | "crossover" | "crossunder";
export type ConditionRhsKind = "indicator" | "value";

export interface ConditionRow {
  /** Stable client-only id for React keys. Not serialised. */
  rowId: string;
  /** Indicator instance id from ``SelectedIndicator.id`` or empty if not yet picked. */
  left: string;
  op: ConditionOp;
  rhsKind: ConditionRhsKind;
  /** Indicator instance id when rhsKind=indicator. */
  right: string;
  /** Numeric RHS when rhsKind=value. */
  value: string;
}

// Operators that *must* be indicator-vs-indicator — crossover/crossunder
// are only meaningful between two series. Pydantic enforces the same
// invariant; we surface it in the UI to avoid the round-trip.
export const SERIES_ONLY_OPS: ReadonlySet<ConditionOp> = new Set([
  "crossover",
  "crossunder",
]);

export const ALL_CONDITION_OPS: ReadonlyArray<ConditionOp> = [
  ">",
  "<",
  ">=",
  "<=",
  "crossover",
  "crossunder",
];

// ─── Risk rules ────────────────────────────────────────────────────────

export interface RiskState {
  /** Empty string = "no cap" (omitted from payload). */
  maxDailyLossPercent: string;
  maxTradesPerDay: string;
  maxLossStreak: string;
  maxCapitalPerTradePercent: string;
}

export const RISK_RANGES = {
  maxDailyLossPercent: { min: 0.5, max: 10, step: 0.5 },
  maxTradesPerDay: { min: 1, max: 20, step: 1 },
  maxLossStreak: { min: 1, max: 10, step: 1 },
  maxCapitalPerTradePercent: { min: 1, max: 50, step: 1 },
} as const;

// ─── Exit rules ────────────────────────────────────────────────────────

export const TARGET_RANGE = { min: 0.5, max: 10, step: 0.5 } as const;
export const STOP_LOSS_RANGE = { min: 0.5, max: 5, step: 0.5 } as const;
export const TRAILING_RANGE = { min: 0.1, max: 5, step: 0.1 } as const;

// ─── Builder state ─────────────────────────────────────────────────────

export type Side = "BUY" | "SELL";

export interface BuilderState {
  name: string;
  side: Side;
  selectedIndicators: SelectedIndicator[];
  conditions: ConditionRow[];
  targetPercent: number;
  stopLossPercent: number;
  trailingEnabled: boolean;
  trailingPercent: number;
  risk: RiskState;
}

export const INITIAL_RISK_STATE: RiskState = {
  maxDailyLossPercent: "",
  maxTradesPerDay: "",
  maxLossStreak: "",
  maxCapitalPerTradePercent: "",
};

export const INITIAL_BUILDER_STATE: BuilderState = {
  name: "",
  side: "BUY",
  selectedIndicators: [],
  conditions: [],
  targetPercent: 2,
  stopLossPercent: 1,
  trailingEnabled: false,
  trailingPercent: 1,
  risk: INITIAL_RISK_STATE,
};

// ─── StrategyJSON output (camelCase aliases) ───────────────────────────

interface IndicatorConditionDsl {
  type: "indicator";
  left: string;
  op: ConditionOp;
  right?: string;
  value?: number;
}

export interface StrategyJsonPayload {
  id: string;
  name: string;
  mode: "intermediate";
  version: 1;
  indicators: { id: string; type: string; params: Record<string, unknown> }[];
  entry: {
    side: Side;
    operator: "AND";
    conditions: IndicatorConditionDsl[];
  };
  exit: {
    targetPercent: number;
    stopLossPercent: number;
    trailingStopPercent?: number;
  };
  risk: {
    maxDailyLossPercent?: number;
    maxTradesPerDay?: number;
    maxLossStreak?: number;
    maxCapitalPerTradePercent?: number;
  };
  execution: {
    mode: "backtest";
    orderType: "MARKET";
    productType: "INTRADAY";
  };
}

// ─── Validation + builder ──────────────────────────────────────────────

/**
 * Returns null when ``state`` is submittable, otherwise a Hinglish
 * sentence the UI can show in-place. Mirrors the Pydantic checks we can
 * cheaply run client-side.
 */
export function validateBuilderState(state: BuilderState): string | null {
  const trimmed = state.name.trim();
  if (!trimmed) return "Strategy ka naam zaroori hai.";
  if (trimmed.length > 256) return "Naam 256 characters se chhota rakho.";

  if (state.selectedIndicators.length === 0) {
    return "Kam se kam ek indicator add karo.";
  }
  const ids = state.selectedIndicators.map((i) => i.id);
  if (new Set(ids).size !== ids.length) {
    return "Indicators ke ids unique hone chahiye.";
  }

  if (state.conditions.length === 0) {
    return "Kam se kam ek entry condition add karo.";
  }

  for (let idx = 0; idx < state.conditions.length; idx++) {
    const c = state.conditions[idx];
    if (!c.left) {
      return `Condition #${idx + 1}: pehla indicator chuno.`;
    }
    if (!ids.includes(c.left)) {
      return `Condition #${idx + 1}: ${c.left} indicators list mein nahi hai.`;
    }
    if (SERIES_ONLY_OPS.has(c.op)) {
      if (c.rhsKind !== "indicator") {
        return `Condition #${idx + 1}: ${c.op} ke liye dusra indicator chahiye, value nahi.`;
      }
      if (!c.right) {
        return `Condition #${idx + 1}: ${c.op} ke liye RHS indicator chuno.`;
      }
      if (!ids.includes(c.right)) {
        return `Condition #${idx + 1}: ${c.right} indicators list mein nahi hai.`;
      }
      if (c.left === c.right) {
        return `Condition #${idx + 1}: same indicator ko khud se compare nahi kar sakte.`;
      }
    } else {
      if (c.rhsKind === "indicator") {
        if (!c.right) {
          return `Condition #${idx + 1}: RHS indicator chuno.`;
        }
        if (!ids.includes(c.right)) {
          return `Condition #${idx + 1}: ${c.right} indicators list mein nahi hai.`;
        }
        if (c.left === c.right) {
          return `Condition #${idx + 1}: same indicator ko khud se compare nahi kar sakte.`;
        }
      } else {
        if (c.value.trim() === "" || Number.isNaN(Number(c.value))) {
          return `Condition #${idx + 1}: ek number value daalo.`;
        }
      }
    }
  }

  if (!(state.targetPercent > 0)) return "Target % zero se zyada hona chahiye.";
  if (state.targetPercent > TARGET_RANGE.max) {
    return `Target % ${TARGET_RANGE.max} se zyada nahi ho sakta.`;
  }
  if (!(state.stopLossPercent > 0)) {
    return "Stop Loss % zero se zyada hona chahiye.";
  }
  if (state.stopLossPercent > STOP_LOSS_RANGE.max) {
    return `Stop Loss % ${STOP_LOSS_RANGE.max} se zyada nahi ho sakta.`;
  }
  if (state.targetPercent <= state.stopLossPercent) {
    return "Target Stop Loss se bada hona chahiye.";
  }

  if (state.trailingEnabled) {
    if (
      !(state.trailingPercent > 0) ||
      state.trailingPercent < TRAILING_RANGE.min ||
      state.trailingPercent > TRAILING_RANGE.max
    ) {
      return `Trailing Stop % ${TRAILING_RANGE.min}-${TRAILING_RANGE.max} ke beech rakho.`;
    }
  }

  const riskError = validateRiskRanges(state.risk);
  if (riskError) return riskError;

  return null;
}

function validateRiskRanges(risk: RiskState): string | null {
  const checks: Array<{
    key: keyof RiskState;
    label: string;
    range: { min: number; max: number };
    integer?: boolean;
  }> = [
    {
      key: "maxDailyLossPercent",
      label: "Max daily loss %",
      range: RISK_RANGES.maxDailyLossPercent,
    },
    {
      key: "maxTradesPerDay",
      label: "Max trades/day",
      range: RISK_RANGES.maxTradesPerDay,
      integer: true,
    },
    {
      key: "maxLossStreak",
      label: "Max loss streak",
      range: RISK_RANGES.maxLossStreak,
      integer: true,
    },
    {
      key: "maxCapitalPerTradePercent",
      label: "Max capital/trade %",
      range: RISK_RANGES.maxCapitalPerTradePercent,
    },
  ];
  for (const check of checks) {
    const raw = risk[check.key].trim();
    if (raw === "") continue;
    const num = Number(raw);
    if (Number.isNaN(num)) return `${check.label}: number daalo.`;
    if (num < check.range.min || num > check.range.max) {
      return `${check.label}: ${check.range.min}-${check.range.max} range mein rakho.`;
    }
    if (check.integer && !Number.isInteger(num)) {
      return `${check.label}: integer hona chahiye.`;
    }
  }
  return null;
}

/**
 * Build a server-ready StrategyJSON payload from the builder state.
 * Caller is responsible for first calling ``validateBuilderState`` —
 * this function trusts the state and only handles serialisation.
 */
export function buildStrategyJson(
  state: BuilderState,
  id: string,
): StrategyJsonPayload {
  const conditions: IndicatorConditionDsl[] = state.conditions.map((c) => {
    const base: IndicatorConditionDsl = {
      type: "indicator",
      left: c.left,
      op: c.op,
    };
    if (c.rhsKind === "indicator") {
      base.right = c.right;
    } else {
      base.value = Number(c.value);
    }
    return base;
  });

  const risk: StrategyJsonPayload["risk"] = {};
  const r = state.risk;
  if (r.maxDailyLossPercent.trim() !== "") {
    risk.maxDailyLossPercent = Number(r.maxDailyLossPercent);
  }
  if (r.maxTradesPerDay.trim() !== "") {
    risk.maxTradesPerDay = Number(r.maxTradesPerDay);
  }
  if (r.maxLossStreak.trim() !== "") {
    risk.maxLossStreak = Number(r.maxLossStreak);
  }
  if (r.maxCapitalPerTradePercent.trim() !== "") {
    risk.maxCapitalPerTradePercent = Number(r.maxCapitalPerTradePercent);
  }

  const exit: StrategyJsonPayload["exit"] = {
    targetPercent: state.targetPercent,
    stopLossPercent: state.stopLossPercent,
  };
  if (state.trailingEnabled) {
    exit.trailingStopPercent = state.trailingPercent;
  }

  return {
    id,
    name: state.name.trim(),
    mode: "intermediate",
    version: 1,
    indicators: state.selectedIndicators.map((ind) => ({
      id: ind.id,
      type: ind.type,
      params: { ...ind.params },
    })),
    entry: { side: state.side, operator: "AND", conditions },
    exit,
    risk,
    execution: {
      mode: "backtest",
      orderType: "MARKET",
      productType: "INTRADAY",
    },
  };
}

// ─── Indicator instance helpers ────────────────────────────────────────

/**
 * Sanitise a metadata's input list so consumers don't have to
 * re-validate the ``unknown[]`` shape that ``IndicatorMetadata`` exposes.
 */
export interface InputSpecLite {
  name: string;
  type: "number" | "source" | "boolean" | "string";
  default: unknown;
  min?: number;
  max?: number;
}

export function readInputSpecs(meta: IndicatorMetadata): InputSpecLite[] {
  const out: InputSpecLite[] = [];
  for (const raw of meta.inputs) {
    if (raw === null || typeof raw !== "object") continue;
    const r = raw as Record<string, unknown>;
    const name = typeof r.name === "string" ? r.name : null;
    const type = r.type;
    if (!name || typeof type !== "string") continue;
    if (type !== "number" && type !== "source" && type !== "boolean" && type !== "string") {
      continue;
    }
    const spec: InputSpecLite = { name, type, default: r.default };
    if (typeof r.min === "number") spec.min = r.min;
    if (typeof r.max === "number") spec.max = r.max;
    out.push(spec);
  }
  return out;
}

/**
 * Build a stable, lower-snake-case instance id like ``ema_20`` /
 * ``rsi_14_2`` (suffix increments on collision so the user can stack
 * multiple instances of the same indicator).
 */
export function makeInstanceId(
  type: string,
  params: Record<string, number | string>,
  taken: ReadonlySet<string>,
): string {
  const periodLike = pickPeriodLike(params);
  const base = periodLike !== null ? `${type}_${periodLike}` : type;
  if (!taken.has(base)) return base;
  let n = 2;
  while (taken.has(`${base}_${n}`)) n++;
  return `${base}_${n}`;
}

function pickPeriodLike(params: Record<string, number | string>): number | string | null {
  // Prefer the most identifying numeric param. ``period`` covers EMA/SMA/RSI;
  // others fall back to first numeric value, then first string.
  if (typeof params.period === "number" || typeof params.period === "string") {
    return params.period;
  }
  for (const [, v] of Object.entries(params)) {
    if (typeof v === "number") return v;
  }
  return null;
}

export function buildIndicatorLabel(
  meta: IndicatorMetadata,
  params: Record<string, number | string>,
): string {
  const periodLike = pickPeriodLike(params);
  if (periodLike !== null && periodLike !== "") {
    return `${meta.name} (${periodLike})`;
  }
  return meta.name;
}

/**
 * Common ``source`` enum values for InputType.SOURCE — the backend
 * doesn't ship the enum in the metadata payload, so the picker offers
 * the canonical OHLCV vocabulary as a hardcoded list.
 */
export const SOURCE_OPTIONS = [
  "close",
  "open",
  "high",
  "low",
  "hl2",
  "hlc3",
  "ohlc4",
] as const;
