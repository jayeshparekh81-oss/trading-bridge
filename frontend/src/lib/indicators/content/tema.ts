import type { IndicatorContent } from "./_types";

export const TEMA: IndicatorContent = {
  slug: "tema",
  name: "TEMA (Triple Exponential Moving Average)",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "EMA-based smoother designed to remove most of the lag inherent in regular EMAs. Single line, faster response.",
  one_liner_hi:
    "EMA-based smoother jo regular EMAs ke inherent lag ko remove karne ke liye design hua. Single line, faster response.",

  description_en:
    "TEMA, created by Patrick Mulloy in 1994, layers three EMAs together with a clever formula that cancels out most of the lag each individual EMA introduces. The math is: TEMA = 3 × EMA - 3 × EMA(EMA) + EMA(EMA(EMA)). The result tracks price more closely than a plain EMA of the same period without becoming noticeably noisier.\n\nDon't confuse TEMA with 'Triple EMA Crossover' (using three separate EMAs of different periods as alignment filter). TEMA is a SINGLE smoothed line that uses three nested EMA calculations internally.\n\nUse cases mirror EMA but with faster reaction: TEMA-9 reacts roughly like EMA-5 in trends, with similar noise levels to EMA-9. Crossovers fire earlier; trend-direction reads turn sooner. Good for active traders who find EMAs too laggy.",
  description_hi:
    "TEMA, Patrick Mulloy ne 1994 mein banaya, teen EMAs ko ek clever formula ke saath layer karta hai jo har individual EMA ka introduce kiya lag cancel karta hai. Math: TEMA = 3 × EMA - 3 × EMA(EMA) + EMA(EMA(EMA)). Result same period ki plain EMA se zyada closely price track karta hai bina noticeably noisier hue.\n\nTEMA ko 'Triple EMA Crossover' ke saath confuse mat karo (teen separate EMAs of different periods alignment filter ki tarah). TEMA EK single smoothed line hai jo teen nested EMA calculations internally use karta hai.\n\nUse cases EMA ko mirror karte but faster reaction ke saath: TEMA-9 trends mein roughly EMA-5 jaisi react karti, similar noise levels EMA-9 ke. Crossovers earlier fire hote; trend-direction reads sooner turn hote. Active traders ke liye accha jinko EMAs zyada laggy lagti hain.",

  formula_explanation:
    "Let E1 = EMA(close, period), E2 = EMA(E1, period), E3 = EMA(E2, period). TEMA = 3×E1 - 3×E2 + E3. Default period: 9. The triple-nesting removes most first- and second-order lag while keeping the smoothing benefit of EMA.",

  default_period: 9,
  period_range: [5, 50],
  common_periods: [9, 14, 21],

  use_cases: [
    {
      scenario: "Faster crossover signals than EMA",
      what_to_do: "Use TEMA-9 / TEMA-21 crossovers instead of EMA-9 / EMA-21 for earlier entry timing",
      why: "Same edge as EMA crossovers but signals fire 1-3 bars earlier on average — meaningful for short-term setups.",
    },
    {
      scenario: "Trend-direction visualisation on intraday charts",
      what_to_do: "Plot TEMA-21 on 5-min intraday for cleaner trend visualisation without slow-EMA lag",
      why: "Intraday traders want fast bias reads; TEMA's reduced lag makes the direction switch obvious sooner.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish TEMA cross",
      condition: "Fast TEMA crosses above slow TEMA",
      action: "Long entry — earlier than equivalent EMA cross.",
    },
    {
      signal: "Bearish TEMA cross",
      condition: "Fast TEMA crosses below slow TEMA",
      action: "Long exit / short.",
    },
  ],

  pitfalls: [
    "Faster reaction means more false crosses in chop. Pair with ADX > 25 to filter.",
    "Some libraries normalize TEMA differently (3×E1 vs E1 weighting alternates). Verify your library matches the formula you intend.",
    "TEMA on long periods (50+) doesn't add much value — at slow periods, EMA's lag is already manageable and TEMA's smoothing pattern flattens out.",
    "Heavier compute than EMA (three nested averages); for high-frequency setups, factor that into latency budgets.",
  ],

  works_well_with: ["adx", "atr", "supertrend"],
  works_poorly_with: ["dema", "ema", "wma"],

  example_strategies: [
    "TEMA Crossover (5-min BANKNIFTY F&O scalp)",
    "TEMA Trend Filter (1h NSE-50 stocks)",
  ],

  indian_context:
    "TEMA suits Indian intraday F&O scalpers on BANKNIFTY 5-min — the index moves quickly and EMA-9 / EMA-21 crosses lag enough to miss the first 1-2% of intraday moves. TEMA closes that gap. On positional daily NIFTY-50 stocks, TEMA offers less benefit because daily timeframes don't reward sub-bar timing precision.",
};
