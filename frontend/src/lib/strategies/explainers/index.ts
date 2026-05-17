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
import { MACD_HISTOGRAM_MOMENTUM } from "./macd-histogram-momentum";
import { BANKNIFTY_WEEKLY_EQUITY } from "./banknifty-weekly-equity";
import { PREMARKET_GAP } from "./premarket-gap";
import { RSI_MACD_CONFLUENCE } from "./rsi-macd-confluence";
import { BB_RSI_OVERSOLD } from "./bb-rsi-oversold";
import { ADX_STRONG_TREND_FILTER } from "./adx-strong-trend-filter";
import { AROON_CROSSOVER } from "./aroon-crossover";
import { BOLLINGER_PCT_B_EXTREME } from "./bollinger-pct-b-extreme";
import { CAMARILLA_PIVOTS_INTRADAY } from "./camarilla-pivots-intraday";
import { CCI_MOMENTUM } from "./cci-momentum";
import { CHANDELIER_EXIT_TRAIL } from "./chandelier-exit-trail";
import { CMF_CONFIRMATION } from "./cmf-confirmation";
import { DOJI_REVERSAL } from "./doji-reversal";
import { DONCHIAN_CHANNEL_BREAKOUT } from "./donchian-channel-breakout";
import { ENGULFING_CANDLE_REVERSAL } from "./engulfing-candle-reversal";
import { FIBONACCI_RETRACEMENT_ENTRY } from "./fibonacci-retracement-entry";
import { HAMMER_HANGING_MAN_PATTERN } from "./hammer-hanging-man-pattern";
import { HEIKIN_ASHI_TREND } from "./heikin-ashi-trend";
import { HULL_MA_TREND } from "./hull-ma-trend";
import { ICHIMOKU_CLOUD_CROSSOVER } from "./ichimoku-cloud-crossover";
import { INSIDE_BAR_BREAKOUT } from "./inside-bar-breakout";
import { KELTNER_CHANNEL_BOUNCE } from "./keltner-channel-bounce";
import { MACD_DIVERGENCE } from "./macd-divergence";
import { MFI_OVERBOUGHT_OVERSOLD } from "./mfi-overbought-oversold";
import { OBV_DIVERGENCE } from "./obv-divergence";
import { PARABOLIC_SAR_REVERSAL } from "./parabolic-sar-reversal";
import { PIVOT_POINT_BOUNCE } from "./pivot-point-bounce";
import { PSAR_EMA_COMBO } from "./psar-ema-combo";
import { RANGE_TRADING_SR } from "./range-trading-sr";
import { RSI_DIVERGENCE } from "./rsi-divergence";


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
  "macd-histogram-momentum": MACD_HISTOGRAM_MOMENTUM,
  "banknifty-weekly-equity": BANKNIFTY_WEEKLY_EQUITY,
  "premarket-gap": PREMARKET_GAP,
  "rsi-macd-confluence": RSI_MACD_CONFLUENCE,
  "bb-rsi-oversold": BB_RSI_OVERSOLD,
  "adx-strong-trend-filter": ADX_STRONG_TREND_FILTER,
  "aroon-crossover": AROON_CROSSOVER,
  "bollinger-pct-b-extreme": BOLLINGER_PCT_B_EXTREME,
  "camarilla-pivots-intraday": CAMARILLA_PIVOTS_INTRADAY,
  "cci-momentum": CCI_MOMENTUM,
  "chandelier-exit-trail": CHANDELIER_EXIT_TRAIL,
  "cmf-confirmation": CMF_CONFIRMATION,
  "doji-reversal": DOJI_REVERSAL,
  "donchian-channel-breakout": DONCHIAN_CHANNEL_BREAKOUT,
  "engulfing-candle-reversal": ENGULFING_CANDLE_REVERSAL,
  "fibonacci-retracement-entry": FIBONACCI_RETRACEMENT_ENTRY,
  "hammer-hanging-man-pattern": HAMMER_HANGING_MAN_PATTERN,
  "heikin-ashi-trend": HEIKIN_ASHI_TREND,
  "hull-ma-trend": HULL_MA_TREND,
  "ichimoku-cloud-crossover": ICHIMOKU_CLOUD_CROSSOVER,
  "inside-bar-breakout": INSIDE_BAR_BREAKOUT,
  "keltner-channel-bounce": KELTNER_CHANNEL_BOUNCE,
  "macd-divergence": MACD_DIVERGENCE,
  "mfi-overbought-oversold": MFI_OVERBOUGHT_OVERSOLD,
  "obv-divergence": OBV_DIVERGENCE,
  "parabolic-sar-reversal": PARABOLIC_SAR_REVERSAL,
  "pivot-point-bounce": PIVOT_POINT_BOUNCE,
  "psar-ema-combo": PSAR_EMA_COMBO,
  "range-trading-sr": RANGE_TRADING_SR,
  "rsi-divergence": RSI_DIVERGENCE,
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
