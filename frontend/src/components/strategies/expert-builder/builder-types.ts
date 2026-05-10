/**
 * Expert-builder shared types, validators, and JSON serialiser/parser.
 *
 * Notes on schema parity:
 *   * The Phase 1 ``StrategyJSON`` schema has a *flat* ``EntryRules.conditions``
 *     list with a single ``operator``. Nested condition groups need a
 *     schema upgrade; the expert UI exposes a single AND/OR group plus
 *     all four condition types (indicator/candle/time/price), which is
 *     the richest expression that round-trips losslessly today.
 *   * ``ExitRules.indicator_exits`` accepts the *same* discriminated
 *     ``Condition`` union as entry, so the same row editor is reused.
 *   * ``ExitRules`` requires *at least one* exit primitive (target,
 *     stopLoss, trailingStop, partialExits, squareOffTime, indicatorExits,
 *     or reverseSignalExit) — we mirror this client-side.
 *   * ``IndicatorCondition`` requires *exactly one* of right/value, and
 *     crossover/crossunder additionally require ``right``. The validator
 *     here enforces the same.
 */
import type { IndicatorMetadata } from "@/components/strategies/indicator-library";

// ─── Constants from the Phase 1 schema ─────────────────────────────────

export type Side = "BUY" | "SELL";
export type EntryOperator = "AND" | "OR";

export const INDICATOR_OPS = [
  ">",
  "<",
  ">=",
  "<=",
  "crossover",
  "crossunder",
] as const;
export type IndicatorOp = (typeof INDICATOR_OPS)[number];
export const SERIES_ONLY_OPS: ReadonlySet<IndicatorOp> = new Set([
  "crossover",
  "crossunder",
]);

export const CANDLE_PATTERNS = [
  "bullish",
  "bearish",
  "engulfing",
  "doji",
  "hammer",
  "shooting_star",
] as const;
export type CandlePattern = (typeof CANDLE_PATTERNS)[number];

export const TIME_OPS = ["after", "before", "between", "exact"] as const;
export type TimeOp = (typeof TIME_OPS)[number];

export const PRICE_OPS = [
  ">",
  "<",
  ">=",
  "<=",
  "previous_high_breakout",
  "previous_low_breakdown",
] as const;
export type PriceOp = (typeof PRICE_OPS)[number];
export const PRICE_COMPARATORS: ReadonlySet<PriceOp> = new Set([
  ">",
  "<",
  ">=",
  "<=",
]);

const HHMM_RE = /^\d{2}:\d{2}$/;

// ─── Indicator instance ────────────────────────────────────────────────

export interface SelectedIndicator {
  id: string;
  type: string;
  label: string;
  params: Record<string, number | string>;
  meta: IndicatorMetadata;
}

// ─── Conditions (4 types — discriminated on ``type``) ──────────────────

export type ConditionRhsKind = "indicator" | "value";

export interface IndicatorConditionRow {
  rowId: string;
  type: "indicator";
  left: string;
  op: IndicatorOp;
  rhsKind: ConditionRhsKind;
  right: string;
  value: string;
}

export interface CandleConditionRow {
  rowId: string;
  type: "candle";
  pattern: CandlePattern;
}

export interface TimeConditionRow {
  rowId: string;
  type: "time";
  op: TimeOp;
  value: string;
  end: string;
}

export interface PriceConditionRow {
  rowId: string;
  type: "price";
  op: PriceOp;
  value: string;
}

export type ConditionRow =
  | IndicatorConditionRow
  | CandleConditionRow
  | TimeConditionRow
  | PriceConditionRow;

export type ConditionType = ConditionRow["type"];

// ─── Partial exits ─────────────────────────────────────────────────────

export interface PartialExitRow {
  rowId: string;
  qtyPercent: string;
  targetPercent: string;
}

// ─── Risk + Exit state ─────────────────────────────────────────────────

export interface RiskState {
  maxDailyLossPercent: string;
  maxTradesPerDay: string;
  maxLossStreak: string;
  maxCapitalPerTradePercent: string;
}

export const RISK_RANGES = {
  maxDailyLossPercent: { min: 0.5, max: 50 },
  maxTradesPerDay: { min: 1, max: 100 },
  maxLossStreak: { min: 1, max: 20 },
  maxCapitalPerTradePercent: { min: 1, max: 100 },
} as const;

export interface ExitState {
  targetPercent: string;
  stopLossPercent: string;
  trailingStopPercent: string;
  squareOffTime: string;
  partialExits: PartialExitRow[];
  indicatorExits: ConditionRow[];
  reverseSignalExit: boolean;
}

// ─── Builder state ─────────────────────────────────────────────────────

export interface RobustnessTestConfig {
  walkForwardEnabled: boolean;
  walkForwardWindows: number;
  sensitivityEnabled: boolean;
  /** Variation as a fraction (0.10 ≡ ±10 %). */
  sensitivityVariation: number;
}

export interface ExpertState {
  name: string;
  side: Side;
  entryOperator: EntryOperator;
  selectedIndicators: SelectedIndicator[];
  conditions: ConditionRow[];
  exit: ExitState;
  risk: RiskState;
  enableRobustnessTest: boolean;
  robustness: RobustnessTestConfig;
}

export const INITIAL_RISK: RiskState = {
  maxDailyLossPercent: "",
  maxTradesPerDay: "",
  maxLossStreak: "",
  maxCapitalPerTradePercent: "",
};

export const INITIAL_EXIT: ExitState = {
  targetPercent: "2",
  stopLossPercent: "1",
  trailingStopPercent: "",
  squareOffTime: "",
  partialExits: [],
  indicatorExits: [],
  reverseSignalExit: false,
};

export const INITIAL_ROBUSTNESS: RobustnessTestConfig = {
  walkForwardEnabled: true,
  walkForwardWindows: 5,
  sensitivityEnabled: false,
  sensitivityVariation: 0.10,
};

export const INITIAL_EXPERT_STATE: ExpertState = {
  name: "",
  side: "BUY",
  entryOperator: "AND",
  selectedIndicators: [],
  conditions: [],
  exit: INITIAL_EXIT,
  risk: INITIAL_RISK,
  enableRobustnessTest: false,
  robustness: INITIAL_ROBUSTNESS,
};

// ─── Output payload (camelCase aliases) ────────────────────────────────

export type ConditionDsl =
  | {
      type: "indicator";
      left: string;
      op: IndicatorOp;
      right?: string;
      value?: number;
    }
  | { type: "candle"; pattern: CandlePattern }
  | { type: "time"; op: TimeOp; value: string; end?: string }
  | { type: "price"; op: PriceOp; value?: number };

export interface PartialExitDsl {
  qtyPercent: number;
  targetPercent: number;
}

export interface StrategyJsonPayload {
  id: string;
  name: string;
  mode: "expert";
  version: 1;
  indicators: { id: string; type: string; params: Record<string, unknown> }[];
  entry: {
    side: Side;
    operator: EntryOperator;
    conditions: ConditionDsl[];
  };
  exit: {
    targetPercent?: number;
    stopLossPercent?: number;
    trailingStopPercent?: number;
    partialExits?: PartialExitDsl[];
    squareOffTime?: string;
    indicatorExits?: ConditionDsl[];
    reverseSignalExit?: boolean;
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

// ─── Validation ────────────────────────────────────────────────────────

/**
 * Returns null when ``state`` is submittable, otherwise a Hinglish-leaning
 * sentence the UI can render in-place. Mirrors the Pydantic checks we can
 * cheaply replicate; the backend remains the source of truth.
 */
export function validateExpertState(state: ExpertState): string | null {
  const trimmed = state.name.trim();
  if (!trimmed) return "Strategy ka naam zaroori hai.";
  if (trimmed.length > 256) return "Naam 256 chars se chhota rakho.";

  if (state.selectedIndicators.length === 0) {
    return "Kam se kam ek indicator chahiye.";
  }
  const ids = state.selectedIndicators.map((i) => i.id);
  if (new Set(ids).size !== ids.length) {
    return "Indicator ids unique hone chahiye.";
  }

  if (state.conditions.length === 0) {
    return "Entry ke liye kam se kam ek condition chahiye.";
  }

  for (let idx = 0; idx < state.conditions.length; idx++) {
    const err = validateConditionRow(state.conditions[idx], ids);
    if (err) return `Entry condition #${idx + 1}: ${err}`;
  }

  for (let idx = 0; idx < state.exit.indicatorExits.length; idx++) {
    const err = validateConditionRow(state.exit.indicatorExits[idx], ids);
    if (err) return `Exit condition #${idx + 1}: ${err}`;
  }

  const exitErr = validateExitRules(state.exit);
  if (exitErr) return exitErr;

  const riskErr = validateRiskState(state.risk);
  if (riskErr) return riskErr;

  return null;
}

function validateConditionRow(
  row: ConditionRow,
  knownIndicatorIds: readonly string[],
): string | null {
  switch (row.type) {
    case "indicator": {
      if (!row.left) return "left indicator chuno.";
      if (!knownIndicatorIds.includes(row.left)) {
        return `${row.left} indicators list mein nahi hai.`;
      }
      if (SERIES_ONLY_OPS.has(row.op)) {
        if (row.rhsKind !== "indicator") {
          return `${row.op} ke liye dusra indicator chahiye, value nahi.`;
        }
      }
      if (row.rhsKind === "indicator") {
        if (!row.right) return "RHS indicator chuno.";
        if (!knownIndicatorIds.includes(row.right)) {
          return `${row.right} indicators list mein nahi hai.`;
        }
        if (row.left === row.right) {
          return "Same indicator ko khud se compare nahi kar sakte.";
        }
      } else {
        if (row.value.trim() === "" || Number.isNaN(Number(row.value))) {
          return "Number value daalo.";
        }
      }
      return null;
    }
    case "candle":
      if (!CANDLE_PATTERNS.includes(row.pattern)) {
        return "Pattern invalid.";
      }
      return null;
    case "time": {
      if (!HHMM_RE.test(row.value)) return "Time HH:MM format mein chahiye.";
      if (row.op === "between") {
        if (!HHMM_RE.test(row.end)) {
          return "between ke liye end (HH:MM) chahiye.";
        }
      } else if (row.end !== "") {
        return `'end' sirf op='between' ke liye allowed hai (op=${row.op}).`;
      }
      return null;
    }
    case "price": {
      if (PRICE_COMPARATORS.has(row.op)) {
        if (row.value.trim() === "" || Number.isNaN(Number(row.value))) {
          return `${row.op} ke liye value (price level) chahiye.`;
        }
      } else if (row.value.trim() !== "") {
        return `${row.op} value use nahi karta — empty rakho.`;
      }
      return null;
    }
  }
}

function validateExitRules(exit: ExitState): string | null {
  const target = parseOptionalPositive(exit.targetPercent);
  const stop = parseOptionalPositive(exit.stopLossPercent);
  const trailing = parseOptionalPositive(exit.trailingStopPercent);

  if (target.error) return `Target %: ${target.error}`;
  if (stop.error) return `Stop Loss %: ${stop.error}`;
  if (trailing.error) return `Trailing Stop %: ${trailing.error}`;

  if (target.value !== null && stop.value !== null) {
    if (target.value <= stop.value) {
      return "Target Stop Loss se bada hona chahiye.";
    }
  }

  if (exit.squareOffTime.trim() !== "" && !HHMM_RE.test(exit.squareOffTime)) {
    return "Square-off time HH:MM format mein hona chahiye.";
  }

  // Validate partial exits — qty% sum to 100 if any present.
  if (exit.partialExits.length > 0) {
    let qtySum = 0;
    for (let idx = 0; idx < exit.partialExits.length; idx++) {
      const p = exit.partialExits[idx];
      const qty = Number(p.qtyPercent);
      const tgt = Number(p.targetPercent);
      if (
        p.qtyPercent.trim() === "" ||
        Number.isNaN(qty) ||
        qty <= 0 ||
        qty > 100
      ) {
        return `Partial exit #${idx + 1}: qty% (0-100] range mein chahiye.`;
      }
      if (
        p.targetPercent.trim() === "" ||
        Number.isNaN(tgt) ||
        tgt <= 0
      ) {
        return `Partial exit #${idx + 1}: target% > 0 chahiye.`;
      }
      qtySum += qty;
    }
    if (Math.abs(qtySum - 100) > 0.01) {
      return `Partial exits ka qty% total 100% hona chahiye (abhi: ${qtySum.toFixed(2)}%).`;
    }
  }

  // Mirror Pydantic: ExitRules requires at least one exit primitive.
  const anyExit =
    target.value !== null ||
    stop.value !== null ||
    trailing.value !== null ||
    exit.partialExits.length > 0 ||
    exit.squareOffTime.trim() !== "" ||
    exit.indicatorExits.length > 0 ||
    exit.reverseSignalExit;
  if (!anyExit) {
    return "Kam se kam ek exit rule (target, stop, trailing, partial, square-off, indicator exit, ya reverse signal) chahiye.";
  }
  return null;
}

function validateRiskState(risk: RiskState): string | null {
  const checks: Array<{
    key: keyof RiskState;
    label: string;
    range: { min: number; max: number };
    integer?: boolean;
  }> = [
    {
      key: "maxDailyLossPercent",
      label: "Max Daily Loss %",
      range: RISK_RANGES.maxDailyLossPercent,
    },
    {
      key: "maxTradesPerDay",
      label: "Max Trades / Day",
      range: RISK_RANGES.maxTradesPerDay,
      integer: true,
    },
    {
      key: "maxLossStreak",
      label: "Max Loss Streak",
      range: RISK_RANGES.maxLossStreak,
      integer: true,
    },
    {
      key: "maxCapitalPerTradePercent",
      label: "Max Capital / Trade %",
      range: RISK_RANGES.maxCapitalPerTradePercent,
    },
  ];
  for (const c of checks) {
    const raw = risk[c.key].trim();
    if (raw === "") continue;
    const num = Number(raw);
    if (Number.isNaN(num)) return `${c.label}: number daalo.`;
    if (num < c.range.min || num > c.range.max) {
      return `${c.label}: ${c.range.min}-${c.range.max} range mein rakho.`;
    }
    if (c.integer && !Number.isInteger(num)) {
      return `${c.label}: integer hona chahiye.`;
    }
  }
  return null;
}

interface ParsedOptional {
  value: number | null;
  error: string | null;
}

function parseOptionalPositive(raw: string): ParsedOptional {
  const trimmed = raw.trim();
  if (trimmed === "") return { value: null, error: null };
  const num = Number(trimmed);
  if (Number.isNaN(num)) return { value: null, error: "number daalo." };
  if (num <= 0) return { value: null, error: "zero se zyada hona chahiye." };
  return { value: num, error: null };
}

// ─── Builder → JSON ────────────────────────────────────────────────────

export function buildStrategyJson(
  state: ExpertState,
  id: string,
): StrategyJsonPayload {
  const conditions = state.conditions.map((row) => conditionRowToDsl(row));
  const indicatorExits = state.exit.indicatorExits.map((row) =>
    conditionRowToDsl(row),
  );

  const exit: StrategyJsonPayload["exit"] = {};
  const t = parseOptionalPositive(state.exit.targetPercent).value;
  const s = parseOptionalPositive(state.exit.stopLossPercent).value;
  const tr = parseOptionalPositive(state.exit.trailingStopPercent).value;
  if (t !== null) exit.targetPercent = t;
  if (s !== null) exit.stopLossPercent = s;
  if (tr !== null) exit.trailingStopPercent = tr;
  if (state.exit.partialExits.length > 0) {
    exit.partialExits = state.exit.partialExits.map((p) => ({
      qtyPercent: Number(p.qtyPercent),
      targetPercent: Number(p.targetPercent),
    }));
  }
  if (state.exit.squareOffTime.trim() !== "") {
    exit.squareOffTime = state.exit.squareOffTime.trim();
  }
  if (indicatorExits.length > 0) exit.indicatorExits = indicatorExits;
  if (state.exit.reverseSignalExit) exit.reverseSignalExit = true;

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

  return {
    id,
    name: state.name.trim(),
    mode: "expert",
    version: 1,
    indicators: state.selectedIndicators.map((ind) => ({
      id: ind.id,
      type: ind.type,
      params: { ...ind.params },
    })),
    entry: {
      side: state.side,
      operator: state.entryOperator,
      conditions,
    },
    exit,
    risk,
    execution: {
      mode: "backtest",
      orderType: "MARKET",
      productType: "INTRADAY",
    },
  };
}

function conditionRowToDsl(row: ConditionRow): ConditionDsl {
  switch (row.type) {
    case "indicator": {
      const base: Extract<ConditionDsl, { type: "indicator" }> = {
        type: "indicator",
        left: row.left,
        op: row.op,
      };
      if (row.rhsKind === "indicator") {
        base.right = row.right;
      } else {
        base.value = Number(row.value);
      }
      return base;
    }
    case "candle":
      return { type: "candle", pattern: row.pattern };
    case "time": {
      const base: Extract<ConditionDsl, { type: "time" }> = {
        type: "time",
        op: row.op,
        value: row.value,
      };
      if (row.op === "between") base.end = row.end;
      return base;
    }
    case "price": {
      const base: Extract<ConditionDsl, { type: "price" }> = {
        type: "price",
        op: row.op,
      };
      if (PRICE_COMPARATORS.has(row.op)) base.value = Number(row.value);
      return base;
    }
  }
}

// ─── JSON → Builder (best-effort apply) ────────────────────────────────

export interface JsonApplyResult {
  state: ExpertState | null;
  error: string | null;
}

/**
 * Parses a raw payload into an ``ExpertState``. ``catalogue`` is needed to
 * rehydrate the indicator label + meta snapshot. Indicators referenced by
 * a non-existent registry id are dropped with an error.
 */
export function applyJsonToState(
  raw: unknown,
  catalogue: ReadonlyArray<IndicatorMetadata>,
): JsonApplyResult {
  if (raw === null || typeof raw !== "object") {
    return { state: null, error: "JSON object expected." };
  }
  const obj = raw as Record<string, unknown>;
  const errors: string[] = [];

  // ─── name / mode / side ───────────────────────────────────────────
  const name = typeof obj.name === "string" ? obj.name : "";
  const sideRaw = readNested(obj, ["entry", "side"]);
  const side: Side = sideRaw === "SELL" ? "SELL" : "BUY";
  const operatorRaw = readNested(obj, ["entry", "operator"]);
  const entryOperator: EntryOperator =
    operatorRaw === "OR" ? "OR" : "AND";

  // ─── indicators ───────────────────────────────────────────────────
  const indicatorsRaw = readArray(obj, "indicators");
  const selected: SelectedIndicator[] = [];
  for (const item of indicatorsRaw) {
    if (!item || typeof item !== "object") continue;
    const it = item as Record<string, unknown>;
    const id = typeof it.id === "string" ? it.id : null;
    const type = typeof it.type === "string" ? it.type : null;
    if (!id || !type) {
      errors.push("Indicator missing id/type.");
      continue;
    }
    const meta = catalogue.find((m) => m.id === type);
    if (!meta) {
      errors.push(`Indicator type "${type}" registry mein nahi hai.`);
      continue;
    }
    const params: Record<string, number | string> = {};
    if (it.params && typeof it.params === "object") {
      for (const [k, v] of Object.entries(it.params as Record<string, unknown>)) {
        if (typeof v === "number" || typeof v === "string") {
          params[k] = v;
        }
      }
    }
    selected.push({
      id,
      type,
      params,
      label: buildIndicatorLabelLocal(meta, params),
      meta,
    });
  }

  // ─── entry conditions ─────────────────────────────────────────────
  const entryConditionsRaw = readArray(obj, "entry", "conditions");
  const conditions: ConditionRow[] = [];
  for (const c of entryConditionsRaw) {
    const row = parseConditionRaw(c, errors);
    if (row) conditions.push(row);
  }

  // ─── exit ─────────────────────────────────────────────────────────
  const exitObj = (obj.exit && typeof obj.exit === "object") ? obj.exit as Record<string, unknown> : {};
  const exit: ExitState = {
    targetPercent: stringFromNumber(exitObj.targetPercent),
    stopLossPercent: stringFromNumber(exitObj.stopLossPercent),
    trailingStopPercent: stringFromNumber(exitObj.trailingStopPercent),
    squareOffTime:
      typeof exitObj.squareOffTime === "string" ? exitObj.squareOffTime : "",
    partialExits: [],
    indicatorExits: [],
    reverseSignalExit: exitObj.reverseSignalExit === true,
  };
  const partialsRaw = Array.isArray(exitObj.partialExits)
    ? (exitObj.partialExits as unknown[])
    : [];
  for (const p of partialsRaw) {
    if (!p || typeof p !== "object") continue;
    const pp = p as Record<string, unknown>;
    exit.partialExits.push({
      rowId: makeId(),
      qtyPercent: stringFromNumber(pp.qtyPercent),
      targetPercent: stringFromNumber(pp.targetPercent),
    });
  }
  const indicatorExitsRaw = Array.isArray(exitObj.indicatorExits)
    ? (exitObj.indicatorExits as unknown[])
    : [];
  for (const c of indicatorExitsRaw) {
    const row = parseConditionRaw(c, errors);
    if (row) exit.indicatorExits.push(row);
  }

  // ─── risk ─────────────────────────────────────────────────────────
  const riskObj = (obj.risk && typeof obj.risk === "object")
    ? (obj.risk as Record<string, unknown>)
    : {};
  const risk: RiskState = {
    maxDailyLossPercent: stringFromNumber(riskObj.maxDailyLossPercent),
    maxTradesPerDay: stringFromNumber(riskObj.maxTradesPerDay),
    maxLossStreak: stringFromNumber(riskObj.maxLossStreak),
    maxCapitalPerTradePercent: stringFromNumber(
      riskObj.maxCapitalPerTradePercent,
    ),
  };

  if (errors.length > 0) {
    return { state: null, error: errors.join(" ") };
  }

  return {
    state: {
      name,
      side,
      entryOperator,
      selectedIndicators: selected,
      conditions,
      exit,
      risk,
      enableRobustnessTest: false,
      robustness: INITIAL_ROBUSTNESS,
    },
    error: null,
  };
}

function parseConditionRaw(
  c: unknown,
  errors: string[],
): ConditionRow | null {
  if (!c || typeof c !== "object") {
    errors.push("Condition object expected.");
    return null;
  }
  const cc = c as Record<string, unknown>;
  const t = cc.type;
  switch (t) {
    case "indicator": {
      const left = typeof cc.left === "string" ? cc.left : "";
      const op = typeof cc.op === "string" ? (cc.op as IndicatorOp) : ">";
      const hasRight = typeof cc.right === "string" && cc.right !== "";
      const hasValue = typeof cc.value === "number";
      return {
        rowId: makeId(),
        type: "indicator",
        left,
        op: INDICATOR_OPS.includes(op) ? op : ">",
        rhsKind: hasRight ? "indicator" : "value",
        right: hasRight ? (cc.right as string) : "",
        value: hasValue ? String(cc.value) : "",
      };
    }
    case "candle": {
      const pattern = typeof cc.pattern === "string"
        ? (cc.pattern as CandlePattern)
        : "bullish";
      return {
        rowId: makeId(),
        type: "candle",
        pattern: CANDLE_PATTERNS.includes(pattern) ? pattern : "bullish",
      };
    }
    case "time": {
      const op = typeof cc.op === "string" ? (cc.op as TimeOp) : "after";
      return {
        rowId: makeId(),
        type: "time",
        op: TIME_OPS.includes(op) ? op : "after",
        value: typeof cc.value === "string" ? cc.value : "",
        end: typeof cc.end === "string" ? cc.end : "",
      };
    }
    case "price": {
      const op = typeof cc.op === "string" ? (cc.op as PriceOp) : ">";
      return {
        rowId: makeId(),
        type: "price",
        op: PRICE_OPS.includes(op) ? op : ">",
        value: typeof cc.value === "number" ? String(cc.value) : "",
      };
    }
    default:
      errors.push(`Unknown condition type: ${String(t)}`);
      return null;
  }
}

function readNested(obj: Record<string, unknown>, path: string[]): unknown {
  let cur: unknown = obj;
  for (const key of path) {
    if (cur === null || typeof cur !== "object") return undefined;
    cur = (cur as Record<string, unknown>)[key];
  }
  return cur;
}

function readArray(obj: Record<string, unknown>, ...path: string[]): unknown[] {
  const v = readNested(obj, path);
  return Array.isArray(v) ? v : [];
}

function stringFromNumber(value: unknown): string {
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  return "";
}

// ─── Indicator instance helpers ────────────────────────────────────────

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
    const t = r.type;
    if (!name || typeof t !== "string") continue;
    if (t !== "number" && t !== "source" && t !== "boolean" && t !== "string") {
      continue;
    }
    const spec: InputSpecLite = { name, type: t, default: r.default };
    if (typeof r.min === "number") spec.min = r.min;
    if (typeof r.max === "number") spec.max = r.max;
    out.push(spec);
  }
  return out;
}

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

function pickPeriodLike(
  params: Record<string, number | string>,
): number | string | null {
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
  return buildIndicatorLabelLocal(meta, params);
}

function buildIndicatorLabelLocal(
  meta: IndicatorMetadata,
  params: Record<string, number | string>,
): string {
  const periodLike = pickPeriodLike(params);
  if (periodLike !== null && periodLike !== "") {
    return `${meta.name} (${periodLike})`;
  }
  return meta.name;
}

export const SOURCE_OPTIONS = [
  "close",
  "open",
  "high",
  "low",
  "hl2",
  "hlc3",
  "ohlc4",
] as const;

export function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `id_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

// ─── Robustness toggle persistence (sessionStorage hand-off) ───────────

export const ROBUSTNESS_STORAGE_PREFIX = "tb_expert_robustness_";

/**
 * Persist the robustness preference for ``strategyId``. The destination
 * backtest page currently sends ``{}`` to ``/strategies/{id}/backtest``;
 * once it picks up this key, it can pass ``include_sensitivity: true``
 * without any wire-format change required here.
 */
export function persistRobustnessPreference(
  strategyId: string,
  enabled: boolean,
): void {
  if (typeof sessionStorage === "undefined") return;
  try {
    sessionStorage.setItem(
      `${ROBUSTNESS_STORAGE_PREFIX}${strategyId}`,
      enabled ? "1" : "0",
    );
  } catch {
    // sessionStorage can throw in strict-storage environments; the toggle
    // is a hand-off, not a functional requirement, so swallow.
  }
}


/** Storage key for the richer Robustness Test Controls config blob.
 *  Distinct from ``ROBUSTNESS_STORAGE_PREFIX`` so the legacy
 *  on/off boolean and the new per-call config don't collide.
 */
export const ROBUSTNESS_CONFIG_STORAGE_PREFIX = "tb_expert_robustness_config_";


/** Persist the full :class:`RobustnessTestConfig` snapshot for the
 *  next backtest run. Same fire-and-forget contract as
 *  :func:`persistRobustnessPreference` — the consumer (the backtest
 *  page, in a later phase) reads via the matching getter below.
 */
export function persistRobustnessConfig(
  strategyId: string,
  config: RobustnessTestConfig,
): void {
  if (typeof sessionStorage === "undefined") return;
  try {
    sessionStorage.setItem(
      `${ROBUSTNESS_CONFIG_STORAGE_PREFIX}${strategyId}`,
      JSON.stringify(config),
    );
  } catch {
    // Swallow — storage failures must not block strategy creation.
  }
}


/** Read the persisted config for ``strategyId`` (or ``null`` when
 *  unset). Used by the backtest page to forward the user's choices
 *  onto ``POST /api/strategies/{id}/backtest``.
 */
export function readRobustnessConfig(
  strategyId: string,
): RobustnessTestConfig | null {
  if (typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(
      `${ROBUSTNESS_CONFIG_STORAGE_PREFIX}${strategyId}`,
    );
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<RobustnessTestConfig>;
    if (
      typeof parsed.walkForwardEnabled !== "boolean" ||
      typeof parsed.walkForwardWindows !== "number" ||
      typeof parsed.sensitivityEnabled !== "boolean" ||
      typeof parsed.sensitivityVariation !== "number"
    ) {
      return null;
    }
    return parsed as RobustnessTestConfig;
  } catch {
    return null;
  }
}
