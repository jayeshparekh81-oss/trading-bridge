/**
 * Strategy explainer registry — single import surface for pages and
 * components that need the layman-language content for an active
 * equity strategy template.
 *
 * Looks up by slug. Returns `null` for unknown slugs so callers can
 * fall back gracefully (e.g. show only the `config_json` shape on
 * templates that haven't been explainer-authored yet).
 *
 * Adding a new explainer:
 *   1. Create `<slug>.ts` exporting a `const <SLUG>: StrategyExplainer`.
 *   2. Import + add to the EXPLAINERS map below.
 *   3. The test (`explainers-registry.test.ts`) auto-asserts shape.
 */

import type { StrategyExplainer } from "./_types";

import { EMA_CROSSOVER_9_21 } from "./ema-crossover-9-21";
import { EMA_CROSSOVER_20_50 } from "./ema-crossover-20-50";
import { MACD_TREND_SIGNAL } from "./macd-trend-signal";
import { SUPERTREND_RIDER } from "./supertrend-rider";
import { RSI_OVERSOLD_BOUNCE } from "./rsi-oversold-bounce";
import { BB_MEAN_REVERSION } from "./bb-mean-reversion";
import { BB_SQUEEZE_BREAKOUT } from "./bb-squeeze-breakout";
import { ORB_15MIN } from "./orb-15min";
import { PDH_PDL_BREAKOUT } from "./pdh-pdl-breakout";
import { VWAP_BOUNCE } from "./vwap-bounce";


export type { StrategyExplainer, ExampleTrade } from "./_types";

// Imports added as each explainer file lands. Empty initial state
// so the file compiles even when authored over many commits.
const EXPLAINERS_MAP: Record<string, StrategyExplainer> = {
  "ema-crossover-9-21": EMA_CROSSOVER_9_21,
  "ema-crossover-20-50": EMA_CROSSOVER_20_50,
  "macd-trend-signal": MACD_TREND_SIGNAL,
  "supertrend-rider": SUPERTREND_RIDER,
  "rsi-oversold-bounce": RSI_OVERSOLD_BOUNCE,
  "bb-mean-reversion": BB_MEAN_REVERSION,
  "bb-squeeze-breakout": BB_SQUEEZE_BREAKOUT,
  "orb-15min": ORB_15MIN,
  "pdh-pdl-breakout": PDH_PDL_BREAKOUT,
  "vwap-bounce": VWAP_BOUNCE,
};

export const EXPLAINERS: Readonly<Record<string, StrategyExplainer>> =
  EXPLAINERS_MAP;

export const EXPLAINER_COUNT = Object.keys(EXPLAINERS).length;

export function getExplainer(slug: string): StrategyExplainer | null {
  return EXPLAINERS[slug] ?? null;
}

export function listExplainers(): StrategyExplainer[] {
  return Object.values(EXPLAINERS);
}
