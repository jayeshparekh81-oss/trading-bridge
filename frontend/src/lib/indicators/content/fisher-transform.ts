import type { IndicatorContent } from "./_types";

export const FISHER_TRANSFORM: IndicatorContent = {
  slug: "fisher-transform",
  name: "Fisher Transform",
  category: "momentum",
  complexity: "advanced",

  one_liner_en:
    "John Ehlers' transform that converts price changes to near-Gaussian distribution, making extremes more reliable signals.",
  one_liner_hi:
    "John Ehlers ka transform jo price changes ko near-Gaussian distribution mein convert karta — extremes ko reliable signals banata.",

  description_en:
    "The Fisher Transform applies an inverse hyperbolic tangent function (atanh) to a normalised price series, converting the typical fat-tailed price-return distribution into something much closer to a Gaussian (bell curve) distribution. Because Gaussian extremes are statistically rare, peaks and troughs in the transformed series mark genuine turning points more reliably than peaks and troughs in raw price or in oscillators like RSI.\n\nThe practical read: Fisher line peaks at major highs and bottoms at major lows. Reversals of the Fisher line — especially when paired with a signal-line cross (Fisher's own SMA / EMA) — give clean reversal entries.\n\nFisher Transform's strength is sharpness — the peaks/troughs are unambiguous and well-defined. Its weakness is that it requires reasonable trending in the underlying price series; on completely flat data it produces noise.",
  description_hi:
    "Fisher Transform ek inverse hyperbolic tangent function (atanh) apply karta normalised price series pe, typical fat-tailed price-return distribution ko Gaussian (bell curve) ke kareeb convert karta. Gaussian extremes statistically rare hote hain isliye transformed series ke peaks aur troughs raw price ya RSI jaise oscillators se zyada reliable turning points mark karte.\n\nPractical read: Fisher line major highs pe peak karti aur major lows pe bottom karti. Fisher line ke reversals — especially Fisher ki khud ki SMA/EMA signal line cross ke saath paired — clean reversal entries dete.\n\nFisher Transform ki strength sharpness hai — peaks/troughs unambiguous aur well-defined. Weakness yeh ki underlying price series mein reasonable trending chahiye; completely flat data pe noise produce karta.",

  formula_explanation:
    "Normalise price to [-1, +1] over `period` window: x = 2 × (high + low) / 2 - min) / (max - min) - 1. Apply atanh: Fisher = 0.5 × ln((1 + x) / (1 - x)). A 1-bar smoothing of x stabilises the result. Default period: 9.",

  default_period: 9,
  period_range: [5, 25],
  common_periods: [9, 14, 21],

  use_cases: [
    {
      scenario: "Sharp reversal detection",
      what_to_do: "Watch for Fisher line extremes (beyond ±2 typically) followed by a turn",
      why: "Fisher's Gaussian-like behaviour makes ±2 extremes rare and statistically meaningful — reversal candidates are well-flagged.",
    },
    {
      scenario: "Signal-line crossover entries",
      what_to_do: "Use Fisher + a 1-bar-lagged Fisher as a fast signal cross pair",
      why: "Cleaner crosses than MACD because the underlying series is normalised — signal interpretation is consistent across symbols.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish Fisher cross",
      condition: "Fisher crosses above its 1-bar-lagged self",
      action: "Long entry candidate; stronger at oversold extremes.",
    },
    {
      signal: "Bearish Fisher cross",
      condition: "Fisher crosses below its 1-bar-lagged self",
      action: "Long exit / short candidate; stronger at overbought extremes.",
    },
    {
      signal: "Fisher extreme",
      condition: "Fisher beyond ±2",
      action: "Watch for upcoming reversal; statistically rare.",
    },
  ],

  pitfalls: [
    "Requires a trending input series to be useful. On flat low-volatility periods, Fisher noise-floors near zero.",
    "Numerator can blow up if max == min in the window (division by zero). Implementations guard for this; verify yours does.",
    "Some libraries use different normalisation (high-low midpoint vs typical price). Verify which.",
    "Period choice has outsize effect on signal frequency. 9 is a common default; 21 is conservative; 5 is twitchy.",
  ],

  works_well_with: ["ema", "supertrend", "atr"],
  works_poorly_with: ["rsi", "stochastic", "cci"],

  example_strategies: [
    "Fisher Reversal Catcher (1h NIFTY F&O)",
    "Fisher + EMA Pullback (daily large-caps)",
  ],

  indian_context:
    "Fisher Transform has a small but devoted following in Indian quant retail — the Gaussian normalisation makes cross-symbol signal comparison cleaner than RSI / Stochastic. On daily NIFTY F&O stocks, Fisher peaks beyond ±2.5 historically correspond to major multi-week tops and bottoms with high reliability. Less useful on indices than on individual stocks because index aggregation already produces near-Gaussian return distributions.",
};
