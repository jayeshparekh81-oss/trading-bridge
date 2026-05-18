import type { IndicatorContent } from "./_types";

export const ALMA: IndicatorContent = {
  slug: "alma",
  name: "ALMA (Arnaud Legoux Moving Average)",
  category: "trend",
  complexity: "advanced",

  one_liner_en:
    "Gaussian-weighted MA with tunable offset and sigma — balances smoothness vs responsiveness via two parameters.",
  one_liner_hi:
    "Gaussian-weighted MA jiska offset aur sigma tunable hai — smoothness aur responsiveness ko do parameters se balance karta.",

  description_en:
    "ALMA (Arnaud Legoux + Dimitrios Kouzis-Loukas, 2009) applies a Gaussian-shaped weighting curve to the moving-average window, but the curve isn't fixed: it has tunable `offset` (centre of mass) and `sigma` (spread).\n\nOffset near 1.0 weights recent bars heavily (fast response). Offset near 0.0 weights older bars heavily (smoother). Default 0.85 is the recommended compromise. Sigma controls how concentrated the weights are around the offset point — smaller sigma = sharper peak = more responsive; larger sigma = wider curve = smoother.\n\nALMA produces visibly smoother lines than EMA at equivalent responsiveness, similar to HMA but with explicit control over the weighting shape. Quant retail uses ALMA when they want to dial in a precise smoothness/lag trade-off via empirical backtesting.",
  description_hi:
    "ALMA (Arnaud Legoux + Dimitrios Kouzis-Loukas, 2009) moving-average window pe Gaussian-shaped weighting curve apply karta, but curve fixed nahi: `offset` (centre of mass) aur `sigma` (spread) tunable hain.\n\nOffset near 1.0 = recent bars heavy weight (fast response). Offset near 0.0 = older bars heavy (smoother). Default 0.85 recommended compromise. Sigma weights ko offset point ke around kitna concentrated hai control karta — smaller sigma = sharper peak = more responsive; larger sigma = wider curve = smoother.\n\nALMA EMA se visibly smoother lines produce karta equivalent responsiveness pe, HMA jaisi but weighting shape pe explicit control ke saath. Quant retail ALMA tab use karta jab precise smoothness/lag trade-off empirical backtesting se dial in karna ho.",

  formula_explanation:
    "For each bar in the window, weight = exp(-(i - m)² / (2 × s²)) where m = offset × (period - 1), s = period / sigma. ALMA = sum(close[i] × weight[i]) / sum(weight[i]). Default: period=9, offset=0.85, sigma=6.",

  default_period: 9,
  period_range: [5, 50],
  common_periods: [9, 21, 50],

  use_cases: [
    {
      scenario: "Tunable replacement for EMA in production strategies",
      what_to_do: "Backtest ALMA-9 with offset=0.85, sigma=6 vs EMA-9 — usually fewer false signals",
      why: "Same lag-window but smoother — and if backtests want more responsiveness, dial offset higher (closer to 1.0).",
    },
    {
      scenario: "Multi-asset universal smoother",
      what_to_do: "Use ALMA as the standard MA across a strategy that runs on multiple symbols",
      why: "Single indicator with consistent tunable behaviour across volatility regimes — no need to swap MA type per symbol.",
    },
  ],

  common_signals: [
    {
      signal: "Price crosses ALMA",
      condition: "Close crosses above ALMA from below",
      action: "Long candidate; equivalent to EMA cross but with smoother false-cross suppression.",
    },
    {
      signal: "ALMA crossover (fast/slow)",
      condition: "Fast ALMA crosses above slow ALMA",
      action: "Trend-shift candidate.",
    },
  ],

  pitfalls: [
    "Three parameters (period, offset, sigma) — more overfitting risk than EMA. Stick to defaults unless backtested.",
    "Different libraries occasionally normalize the weight sum differently. Verify against a reference.",
    "Less widely discussed than EMA/HMA in Indian retail — community setup-sharing thin.",
    "Tuning offset close to 1.0 makes ALMA almost identical to the price itself (very twitchy); near 0.0 makes it almost identical to SMA (very laggy).",
  ],

  works_well_with: ["adx", "atr", "supertrend"],
  works_poorly_with: ["ema", "wma", "hma"],

  example_strategies: [
    "ALMA Crossover (daily F&O stocks)",
    "ALMA-Tuned Trend Filter (multi-symbol portfolio)",
  ],

  indian_context:
    "ALMA's tunability appeals to Indian quant retail building multi-symbol systems where one MA type needs to perform across different volatility regimes (NIFTY low-vol vs BANKNIFTY high-vol). Default 0.85/6 settings work well as a starting point; backtest-tuning offset to 0.9 sometimes helps on fast-moving F&O stocks during earnings season.",
};
