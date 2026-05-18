import type { IndicatorContent } from "./_types";

export const ULTIMATE_OSCILLATOR: IndicatorContent = {
  slug: "ultimate-oscillator",
  name: "Ultimate Oscillator (UO)",
  category: "momentum",
  complexity: "intermediate",

  one_liner_en:
    "Larry Williams' three-timeframe momentum oscillator on a 0-100 scale. Filters single-timeframe whipsaws.",
  one_liner_hi:
    "Larry Williams ka teen-timeframe momentum oscillator 0-100 scale pe. Single-timeframe whipsaws filter karta.",

  description_en:
    "The Ultimate Oscillator combines three different look-back windows (typically 7, 14, 28 bars) into a single 0-100 oscillator. By averaging momentum from short, medium, and long windows, UO suppresses the false signals that single-period oscillators (RSI, Stochastic) generate.\n\nThe core idea: 'buying pressure' for each bar = close - min(prev_close, low). Sum BP and TR over each of the three windows; the three ratios are weighted (typically 4 / 2 / 1 for fast/medium/slow) and scaled to 0-100.\n\nClassic signal: bullish divergence + UO < 30 + UO breaks above the divergence's intermediate high. The triple-condition makes UO entries rarer than RSI entries but historically higher quality.\n\nUO is less common in modern Indian retail than RSI / MACD, but its multi-timeframe averaging is a real edge — a single chart-panel indicator that effectively does what multi-timeframe analysis attempts.",
  description_hi:
    "Ultimate Oscillator teen different look-back windows (typically 7, 14, 28 bars) ko ek 0-100 oscillator mein combine karta. Short, medium, long windows ka momentum average karke UO un false signals ko suppress karta jo single-period oscillators (RSI, Stochastic) generate karte.\n\nCore idea: har bar ke liye 'buying pressure' = close - min(prev_close, low). Teen windows mein BP aur TR sum karo; teen ratios ko weight do (typically 4 / 2 / 1 fast/medium/slow ke liye) aur 0-100 mein scale karo.\n\nClassic signal: bullish divergence + UO < 30 + UO divergence ki intermediate high ke upar break kare. Triple-condition UO entries ko RSI entries se rare banata but historically higher quality.\n\nUO modern Indian retail mein RSI/MACD se kam common, but uska multi-timeframe averaging real edge hai — single chart-panel indicator jo effectively multi-timeframe analysis ki tarah kaam karta.",

  formula_explanation:
    "BP = close - min(low, prev_close). TR = max(high, prev_close) - min(low, prev_close). For each window n in (7, 14, 28): avg_n = sum(BP, n) / sum(TR, n). UO = 100 × (4 × avg_7 + 2 × avg_14 + avg_28) / (4 + 2 + 1). Default periods: 7, 14, 28.",

  default_period: 14,
  period_range: [5, 50],
  common_periods: [7, 14, 28],

  use_cases: [
    {
      scenario: "High-conviction reversal entries via triple-condition rule",
      what_to_do: "Enter long ONLY on: bullish divergence + UO < 30 + UO break above the intermediate high during divergence",
      why: "Three conditions filter most random divergence noise — fewer entries but historically high win rate.",
    },
    {
      scenario: "Multi-timeframe momentum sanity check",
      what_to_do: "Compare UO read to RSI on the same chart — when they disagree, UO is usually more reliable because it's already multi-timeframe",
      why: "RSI on a single period can flag overbought when longer-window momentum still has room. UO captures both.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish divergence (triple-condition)",
      condition: "Price lower low + UO higher low + UO < 30 at the second low + UO breaks above intermediate high",
      action: "High-conviction long entry.",
    },
    {
      signal: "Overbought rejection",
      condition: "UO crosses below 70 from above",
      action: "Long exit / cautious short.",
    },
  ],

  pitfalls: [
    "Triple-condition setup fires rarely (a few times per year on liquid F&O stocks). Don't force trades when conditions aren't all met.",
    "Default 4/2/1 weights are conventions; some libraries use different ratios. Verify yours.",
    "Like all multi-timeframe indicators, UO trades signal frequency for signal quality — wrong tool for active scalping.",
  ],

  works_well_with: ["ema", "supertrend", "atr"],
  works_poorly_with: ["rsi", "stochastic", "williams-r"],

  example_strategies: [
    "UO Triple-Condition Reversal (daily F&O)",
    "UO Multi-Timeframe Bias Filter (positional)",
  ],

  indian_context:
    "UO on daily NSE F&O stocks is a niche but high-quality setup-generator for swing traders who can stand to wait for rare A+ entries. The triple-condition bullish-divergence setup historically fires 4-8 times per year on a typical large-cap; most attempts cluster around earnings + macro events. Less useful on indices because aggregation already produces multi-timeframe smoothing implicitly.",
};
