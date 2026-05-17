import type { IndicatorContent } from "./_types";

export const BALANCE_OF_POWER: IndicatorContent = {
  slug: "balance-of-power",
  name: "Balance of Power (BOP)",
  category: "momentum",
  complexity: "beginner",

  one_liner_en:
    "Single-bar measure of how much of the range was driven by buyers vs sellers. Range -1 to +1.",
  one_liner_hi:
    "Single-bar measure ki range ka kitna hissa buyers vs sellers ne drive kiya. Range -1 se +1.",

  description_en:
    "Balance of Power compares the close-minus-open distance to the high-minus-low range, on a single-bar basis. Positive means buyers controlled the bar (close ended high in the range); negative means sellers controlled. The raw output is in [-1, +1] per bar.\n\nRaw BOP is noisy, so most traders apply a smoothing MA (typically 14-bar SMA or EMA) to read 'who's been winning' over a window. Sustained positive BOP = ongoing bullish pressure; sustained negative = bearish pressure.\n\nBOP doesn't capture volume — a 0.95 BOP on light volume isn't the same as 0.95 on heavy volume. Pair with volume confirmation (OBV, volume-spike) for high-confidence signals.\n\nUseful as a regime-confirming oscillator next to RSI / MFI — three independent angles on the same 'are we in an uptrend' question. Disagreement = caution.",
  description_hi:
    "Balance of Power close-minus-open distance ko high-minus-low range se compare karta single-bar basis pe. Positive matlab buyers ne bar control kiya (close range mein high khatam); negative matlab sellers ne control kiya. Raw output [-1, +1] mein per bar.\n\nRaw BOP noisy hai isliye most traders smoothing MA apply karte (typically 14-bar SMA ya EMA) 'kaun jeet raha' over a window read karne ke liye. Sustained positive BOP = ongoing bullish pressure; sustained negative = bearish pressure.\n\nBOP volume capture nahi karta — light volume pe 0.95 BOP heavy volume ke 0.95 BOP jaisa nahi hai. Volume confirmation (OBV, volume-spike) ke saath pair karo high-confidence signals ke liye.\n\nRSI/MFI ke baju regime-confirming oscillator ki tarah useful — same 'are we in uptrend' question ke teen independent angles. Disagreement = caution.",

  formula_explanation:
    "BOP_raw = (close - open) / (high - low). Output in [-1, +1] for each bar. Smoothed via SMA or EMA of `period` bars for actionable read. Default smoothing period: 14.",

  default_period: 14,
  period_range: [5, 50],
  common_periods: [9, 14, 21],

  use_cases: [
    {
      scenario: "Regime confirmation alongside RSI / MFI",
      what_to_do: "Long bias when SMA(BOP, 14) > 0 AND RSI > 50 AND MFI > 50",
      why: "Three independent oscillators agreeing = high-conviction regime read.",
    },
    {
      scenario: "Bar-by-bar buying-pressure visualisation",
      what_to_do: "Plot raw BOP histogram below price — bright green spikes = strong buying bars",
      why: "Visual heuristic for which bars drove the move, useful for confirming breakout quality.",
    },
  ],

  common_signals: [
    {
      signal: "BOP zero-line cross up",
      condition: "Smoothed BOP crosses above 0",
      action: "Bullish regime confirmation.",
    },
    {
      signal: "Strong-bar BOP spike",
      condition: "Raw BOP > 0.7 with high volume",
      action: "High-conviction continuation signal.",
    },
  ],

  pitfalls: [
    "Raw BOP is too noisy to trade unfiltered. Always smooth.",
    "Volume-blind — a 0.9 BOP on 100 shares means nothing. Pair with volume.",
    "Doji bars (close ≈ open) produce near-zero BOP that's information-poor.",
    "Division by zero when high == low (rare but happens on illiquid stocks during long pauses).",
  ],

  works_well_with: ["rsi", "mfi", "obv", "volume-profile"],
  works_poorly_with: ["stochastic", "williams-r"],

  example_strategies: [
    "BOP + RSI + MFI Triple-Confirm (daily F&O)",
    "Raw BOP Bar-Quality Filter (intraday)",
  ],

  indian_context:
    "BOP on daily NSE F&O stocks confirms or contradicts RSI / MFI reads — useful as the third leg of a multi-indicator filter. On Indian intraday, raw BOP spikes during the 09:30-10:15 IST window reliably flag opening-drive trends (when the early move sticks). Less informative during 12:00-14:00 IST lunchtime chop.",
};
