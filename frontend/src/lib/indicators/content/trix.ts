import type { IndicatorContent } from "./_types";

export const TRIX: IndicatorContent = {
  slug: "trix",
  name: "TRIX (Triple-Smoothed Exponential Oscillator)",
  category: "momentum",
  complexity: "intermediate",

  one_liner_en:
    "Rate-of-change of a triple-smoothed EMA. Strips out price-cycles shorter than the period — clean trend-momentum read.",
  one_liner_hi:
    "Triple-smoothed EMA ka rate-of-change. Period se shorter price-cycles strip out karta — clean trend-momentum read.",

  description_en:
    "TRIX (Jack Hutson, 1980s) takes the EMA of an EMA of an EMA of price, then computes the percent-rate-of-change of that triple-smoothed value. The triple smoothing acts as a band-pass filter that removes price cycles shorter than the chosen period, leaving only the dominant trend rhythm.\n\nThe practical output looks much like MACD — an oscillator that swings around zero, with positive values during uptrends and negative during downtrends. The triple smoothing makes TRIX less reactive than MACD; signals fire later but with fewer whipsaws.\n\nThe canonical signals are zero-line crosses (trend regime change), signal-line crossovers (TRIX vs an EMA of TRIX), and divergence. TRIX divergence on weekly charts is positioned as a major-top / major-bottom warning — confirm on your own data before relying on it.\n\nTRIX shines on longer-term timeframes (weekly, monthly) where its smoothing matches the rhythm of macro moves. On intraday charts, the lag from triple smoothing makes it less competitive vs faster oscillators.",
  description_hi:
    "TRIX (Jack Hutson, 1980s) price ki EMA ki EMA ki EMA leta hai, phir us triple-smoothed value ka percent-rate-of-change compute karta. Triple smoothing band-pass filter ki tarah kaam karta jo chosen period se shorter price cycles remove karta, sirf dominant trend rhythm leaving.\n\nPractical output MACD jaisi dikhti — ek oscillator jo zero ke around swing karta, uptrends mein positive aur downtrends mein negative. Triple smoothing TRIX ko MACD se kam reactive banata; signals later fire hote but fewer whipsaws ke saath.\n\nCanonical signals zero-line crosses (trend regime change), signal-line crossovers (TRIX vs TRIX ki EMA), aur divergence. Weekly charts pe TRIX divergence ko major-top / major-bottom warning ke roop mein positioned kiya jaata — apne data pe confirm karne ke baad hi rely karo.\n\nTRIX longer-term timeframes (weekly, monthly) pe shine karta jahan uska smoothing macro moves ke rhythm se match karta. Intraday charts pe triple smoothing ka lag faster oscillators ke against less competitive banata.",

  formula_explanation:
    "EMA1 = EMA(close, period). EMA2 = EMA(EMA1, period). EMA3 = EMA(EMA2, period). TRIX = 100 × (EMA3 - EMA3[1]) / EMA3[1]. Signal line is typically a 9-period EMA of TRIX. Default period: 14.",

  default_period: 14,
  period_range: [5, 50],
  common_periods: [9, 14, 21],

  use_cases: [
    {
      scenario: "Long-term swing-trade entries on weekly charts",
      what_to_do: "Long when TRIX crosses above 0 on the weekly chart of a NIFTY F&O stock; exit when it crosses below",
      why: "Triple smoothing on weekly = filter for multi-month trends. Few signals per year but high win rate historically.",
    },
    {
      scenario: "Major-top divergence detection",
      what_to_do: "On weekly index charts, watch for price new high paired with TRIX lower high — major top warning",
      why: "TRIX divergence on weekly charts is conventionally framed as a major-top warning — back-test the specific pattern on recent NIFTY data before sizing positions on the signal alone.",
    },
  ],

  common_signals: [
    {
      signal: "TRIX zero cross up",
      condition: "TRIX crosses above 0",
      action: "Bullish regime — long entry candidate (positional).",
    },
    {
      signal: "TRIX signal-line cross",
      condition: "TRIX crosses above its 9-period EMA",
      action: "Short-cycle bullish momentum.",
    },
    {
      signal: "Bearish TRIX divergence",
      condition: "Price new high + TRIX lower high (weekly or daily timeframe)",
      action: "Heads-up for reversal; tighten stops.",
    },
  ],

  pitfalls: [
    "Triple smoothing = more lag. Don't use TRIX on intraday or for tight stop-loss timing.",
    "Different libraries occasionally compute percent change differently (vs absolute change). Verify your output normalisation.",
    "On flat-line markets, TRIX hovers near zero and provides no signal — wait for trending environments.",
    "Less popular than MACD in Indian retail; community setup-sharing is thinner.",
  ],

  works_well_with: ["ema", "supertrend", "atr"],
  works_poorly_with: ["macd", "stochastic", "tsi"],

  example_strategies: [
    "Weekly TRIX Zero-Cross (positional NIFTY F&O)",
    "TRIX Divergence at 52-Week Highs (weekly indices)",
  ],

  indian_context:
    "Weekly TRIX on NIFTY index data is positioned as a clean macro-trend indicator — zero-line crosses correspond to rare multi-quarter regime shifts; the rarity is the point. Back-test against your specific historical window to validate which past regime shifts the indicator actually marked. For F&O stocks during long sector cycles, weekly TRIX can sometimes flag sector-rotation bottoms ahead of price; confirm with volume and macro context.",
};
