import type { IndicatorContent } from "./_types";

export const ZLEMA: IndicatorContent = {
  slug: "zlema",
  name: "ZLEMA (Zero-Lag Exponential Moving Average)",
  category: "trend",
  complexity: "advanced",

  one_liner_en:
    "EMA variant that pre-emptively offsets the lag by adding a momentum term. Closer-to-realtime than EMA/DEMA.",
  one_liner_hi:
    "EMA variant jo lag ko pre-emptively offset karta hai momentum term add karke. EMA/DEMA se zyada realtime-friendly.",

  description_en:
    "ZLEMA (designed by John Ehlers in 2000) takes a different approach to lag reduction than DEMA/TEMA. Instead of nested smoothing, it pre-adjusts the input series by adding the difference between current price and an earlier-shifted price, effectively projecting forward the recent momentum before feeding it to a regular EMA.\n\nFormula essence: lag = (period - 1) / 2. error = close - close[lag bars ago]. ZLEMA = EMA(close + error, period).\n\nThis 'momentum injection' makes ZLEMA visually appear to lead price slightly during trends — useful for very-fast crossover systems. In ranging markets, ZLEMA can overshoot at turn points because the momentum term keeps pushing in the prior direction for a bar or two.\n\nZLEMA is most useful when you specifically want the fastest possible smoothed trend line and accept the trade-off of occasional overshoot at reversals.",
  description_hi:
    "ZLEMA (John Ehlers ne 2000 mein design ki) DEMA/TEMA se different approach use karti lag reduction ke liye. Nested smoothing ke bajaye, input series ko pre-adjust karti current price aur earlier-shifted price ke difference se, effectively recent momentum forward project karke regular EMA ko feed karne se pehle.\n\nFormula essence: lag = (period - 1) / 2. error = close - close[lag bars ago]. ZLEMA = EMA(close + error, period).\n\nYeh 'momentum injection' ZLEMA ko visually slightly lead karta dikhata trends mein — very-fast crossover systems ke liye useful. Ranging markets mein turn points pe ZLEMA overshoot kar sakti hai kyunki momentum term prior direction mein push karta rehta ek-do bar tak.\n\nZLEMA tab most useful jab specifically fastest possible smoothed trend line chahiye aur reversal pe occasional overshoot accept hai.",

  formula_explanation:
    "lag = (period - 1) / 2. Build a 'lag-corrected' source: src' = close + (close - close[lag bars ago]). Then ZLEMA = EMA(src', period). Default period: 21.",

  default_period: 21,
  period_range: [5, 50],
  common_periods: [14, 21, 34],

  use_cases: [
    {
      scenario: "Fastest-possible trend-line for intraday breakout systems",
      what_to_do: "Use ZLEMA-21 as the dynamic trend line and trade price breaks of it",
      why: "ZLEMA reacts to breakouts within 1-2 bars where EMA-21 would lag by 4-5. Critical for breakout setups where late entry is no entry.",
    },
    {
      scenario: "Fast crossover signal generator",
      what_to_do: "ZLEMA-9 / ZLEMA-21 crossover for sub-2-bar trend-shift detection",
      why: "Fastest crossover MA pair available; trades off some quiet-market reliability for trending-market speed.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish ZLEMA cross",
      condition: "Fast ZLEMA crosses above slow ZLEMA",
      action: "Long entry — earliest practical trend-shift signal.",
    },
    {
      signal: "Price reclaim",
      condition: "Price closes above ZLEMA after a pullback in an uptrend",
      action: "Continuation long.",
    },
  ],

  pitfalls: [
    "Overshoots at reversal points. Tight stops are essential to limit damage.",
    "Period choice changes the lag-correction strength. Very short periods (5-7) make ZLEMA almost identical to price itself.",
    "Implementation variants exist (different lag formulas). Pick a library and stick with it.",
    "Less popular in Indian retail than EMA / TEMA — community setup-sharing is thin.",
  ],

  works_well_with: ["adx", "atr", "supertrend"],
  works_poorly_with: ["ema", "tema", "dema"],

  example_strategies: [
    "ZLEMA Breakout Catcher (15m NIFTY)",
    "ZLEMA Crossover (5m BANKNIFTY scalp)",
  ],

  indian_context:
    "ZLEMA's overshoot-prone behaviour pairs poorly with NIFTY's mid-day chop tendency. On BANKNIFTY's faster trend days, ZLEMA shines — it catches the day's directional move 1-2 bars earlier than EMA. Best as the entry-trigger pair rather than the bias-filter pair (where slower EMAs are better at separating regime from noise).",
};
