import type { IndicatorContent } from "./_types";

export const CHANDE_MOMENTUM_OSCILLATOR: IndicatorContent = {
  slug: "chande-momentum-oscillator",
  name: "Chande Momentum Oscillator (CMO)",
  category: "momentum",
  complexity: "intermediate",

  one_liner_en:
    "RSI's older cousin — bounded -100 to +100 (vs RSI 0-100). Same conceptual purpose, different scaling.",
  one_liner_hi:
    "RSI ka older cousin — bounded -100 se +100 (vs RSI 0-100). Same conceptual purpose, different scaling.",

  description_en:
    "Tushar Chande designed CMO in the early 1990s. The formula is conceptually identical to RSI's: compare the sum of recent up-moves to the sum of recent down-moves. But CMO scales the result to -100/+100 instead of 0/100, and uses ALL recent bars (not just up OR down bars in the denominator).\n\nThe practical differences vs RSI:\n- ±50 thresholds (CMO's overbought/oversold) instead of 70/30 (RSI).\n- Zero-line cross is the centerline (vs RSI's 50 line).\n- Range -100 to +100 reads more like MACD intuitively for some.\n\nFunctionally, CMO and RSI deliver similar signals on the same chart — choosing between them is mostly an aesthetic / habit preference. Some quant retail prefers CMO for the symmetric range and zero centerline; most traditional retail still uses RSI for the same reason (familiarity).",
  description_hi:
    "Tushar Chande ne CMO 1990s ke early mein design ki. Formula conceptually RSI ki identical: recent up-moves ke sum ko recent down-moves ke sum se compare karo. But CMO result ko 0/100 ke bajaye -100/+100 mein scale karta, aur denominator mein ALL recent bars use karta (sirf up ya down bars nahi).\n\nRSI vs practical differences:\n- ±50 thresholds (CMO ke overbought/oversold) instead of 70/30 (RSI).\n- Zero-line cross centerline hai (vs RSI ki 50 line).\n- Range -100 se +100 kuch ke liye MACD jaisi intuitive lagti.\n\nFunctionally, CMO aur RSI same chart pe similar signals deliver karte — choose karna mostly aesthetic / habit preference. Quant retail kuch CMO prefer karte symmetric range + zero centerline ke liye; traditional retail mostly RSI use karta familiarity ke liye.",

  formula_explanation:
    "Over `period` bars: sum_up = sum of (close[i] - close[i-1]) where positive. sum_down = sum of |close[i] - close[i-1]| where negative. CMO = 100 × (sum_up - sum_down) / (sum_up + sum_down). Default period: 14.",

  default_period: 14,
  period_range: [5, 50],
  common_periods: [9, 14, 21],

  use_cases: [
    {
      scenario: "Drop-in RSI replacement with symmetric range",
      what_to_do: "Use CMO(14) with ±50 thresholds anywhere RSI(14) with 30/70 is currently used",
      why: "Same edge, symmetric reading. Some traders find ±50 easier to mentally compare than 70/30.",
    },
    {
      scenario: "Centerline (zero) bias filter",
      what_to_do: "Long bias when CMO > 0; short bias when CMO < 0",
      why: "Single-condition trend regime filter; cleaner than RSI's 50-line cross because the centerline is the natural zero.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish CMO cross",
      condition: "CMO crosses above -50 from below",
      action: "Long entry candidate — oversold reversal.",
    },
    {
      signal: "Bearish CMO cross",
      condition: "CMO crosses below +50 from above",
      action: "Long exit / short.",
    },
    {
      signal: "CMO zero cross",
      condition: "CMO crosses 0",
      action: "Momentum regime shift; bias filter trigger.",
    },
  ],

  pitfalls: [
    "Nearly identical to RSI in practice — using BOTH adds no new information.",
    "Strong trends pin CMO at extremes (like RSI). Don't fight trends with CMO ±50 reversal logic.",
    "Less popular in Indian retail than RSI — community setup-sharing thin.",
    "Different libraries occasionally normalize CMO differently. Verify.",
  ],

  works_well_with: ["ema", "macd", "supertrend"],
  works_poorly_with: ["rsi", "stochastic", "williams-r"],

  example_strategies: [
    "CMO Oversold Reversal (daily F&O stocks)",
    "CMO Zero-Cross Bias Filter (positional)",
  ],

  indian_context:
    "CMO has a smaller following than RSI in Indian retail. Quant-leaning traders sometimes prefer it for the symmetric ±100 range when scripting custom alerts (mental math easier than 0-100 with 30/70 thresholds). On daily NIFTY F&O stocks, CMO(14) produces qualitatively identical signals to RSI(14) — pick the one your charting setup is comfortable with.",
};
