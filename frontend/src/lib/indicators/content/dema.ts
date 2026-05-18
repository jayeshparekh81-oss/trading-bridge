import type { IndicatorContent } from "./_types";

export const DEMA: IndicatorContent = {
  slug: "dema",
  name: "DEMA (Double Exponential Moving Average)",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "EMA with most of the lag removed via a single subtraction. Between EMA and TEMA in responsiveness.",
  one_liner_hi:
    "EMA jisme zyaadar lag ek single subtraction se remove ho gaya. Responsiveness mein EMA aur TEMA ke beech.",

  description_en:
    "DEMA (also from Patrick Mulloy, 1994 — same paper as TEMA) uses a simpler two-pass formula: DEMA = 2 × EMA - EMA(EMA). The subtraction cancels the bulk of the lag that the inner EMA introduces, while the outer doubling preserves the smoothing.\n\nDEMA sits between regular EMA (laggy but smooth) and TEMA (fastest but slightly noisier). For traders who find EMA too slow but TEMA too eager to flip, DEMA is the middle option.\n\nFormulaically and conceptually, DEMA is simpler than TEMA — only two EMAs nested rather than three. The compute cost is correspondingly lower, which matters if you're computing on a wide universe of symbols.",
  description_hi:
    "DEMA (Patrick Mulloy se hi, 1994 — same paper as TEMA) simpler two-pass formula use karta hai: DEMA = 2 × EMA - EMA(EMA). Subtraction inner EMA ka introduce kiya lag cancel karta hai, while outer doubling smoothing preserve karta hai.\n\nDEMA regular EMA (laggy but smooth) aur TEMA (fastest but slightly noisier) ke beech baithta hai. Jo traders EMA ko zyada slow aur TEMA ko zyada eager paate, unke liye DEMA middle option hai.\n\nFormula aur concept ki tarah DEMA TEMA se simpler hai — sirf do EMAs nested, teen nahi. Compute cost bhi correspondingly kam, jo matter karta hai wide symbol universe ke liye.",

  formula_explanation:
    "DEMA = 2 × EMA(close, period) - EMA(EMA(close, period), period). Default period: 9. Removes most first-order lag via the subtraction; second-order lag persists (which TEMA further suppresses with a third nested EMA).",

  default_period: 9,
  period_range: [5, 50],
  common_periods: [9, 14, 21],

  use_cases: [
    {
      scenario: "Crossover trading with EMA-like smoothness but faster timing",
      what_to_do: "Replace EMA-9 / EMA-21 crossovers with DEMA-9 / DEMA-21 — same edge, ~1-2 bars earlier",
      why: "DEMA's lag reduction is modest enough to keep noise low while still beating EMA for entry timing.",
    },
    {
      scenario: "Stop-loss reference line under trends",
      what_to_do: "Use DEMA-21 as a dynamic stop reference — exit when price crosses below",
      why: "DEMA's faster reaction triggers exits earlier than EMA, locking in more of a winning trade before reversal.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish DEMA cross",
      condition: "Fast DEMA crosses above slow DEMA",
      action: "Long entry candidate.",
    },
    {
      signal: "Bearish DEMA cross",
      condition: "Fast DEMA crosses below slow DEMA",
      action: "Long exit / short candidate.",
    },
    {
      signal: "Price reclaim of DEMA",
      condition: "Price closes back above DEMA after a pullback",
      action: "Continuation long.",
    },
  ],

  pitfalls: [
    "Faster reaction means more false crosses in chop. Filter with ADX > 25.",
    "Doesn't fully cancel lag (TEMA does it better). If you need maximum reactivity, use TEMA; if you need maximum smoothness, use plain EMA.",
    "DEMA on weekly timeframes converges with EMA in behaviour — the lag-reduction benefit fades at longer periods.",
  ],

  works_well_with: ["adx", "atr", "supertrend"],
  works_poorly_with: ["ema", "tema", "wma"],

  example_strategies: [
    "DEMA Crossover (15-min NIFTY F&O)",
    "DEMA Trailing Stop (positional swing)",
  ],

  indian_context:
    "DEMA's middle-ground between EMA and TEMA suits Indian retail's daily swing-trading on NSE F&O stocks better than either extreme. DEMA-50 on the daily catches trend regime changes meaningfully earlier than EMA-50 without producing the false-flip count that TEMA-50 sometimes does. For BANKNIFTY 5-min intraday, prefer TEMA; for daily swing, DEMA is the smart middle.",
};
