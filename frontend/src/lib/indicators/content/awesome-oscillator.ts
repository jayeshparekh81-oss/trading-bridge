import type { IndicatorContent } from "./_types";

export const AWESOME_OSCILLATOR: IndicatorContent = {
  slug: "awesome-oscillator",
  name: "Awesome Oscillator (AO)",
  category: "momentum",
  complexity: "beginner",

  one_liner_en:
    "5-period SMA of midpoints minus 34-period SMA of midpoints. Histogram form. Bill Williams' momentum staple.",
  one_liner_hi:
    "Midpoints ki 5-period SMA minus 34-period SMA. Histogram form. Bill Williams ka momentum staple.",

  description_en:
    "AO is conceptually a 'momentum MACD' — the difference between a fast and a slow SMA, plotted as a histogram around the zero line. Difference vs MACD: AO uses 5/34 periods (much shorter than MACD's 12/26) and applies them to (high+low)/2 rather than close.\n\nThe zero line is the regime divider: AO > 0 = bullish momentum, AO < 0 = bearish. Within each regime, the colour of the histogram bars tells you the immediate direction: green bar = momentum strengthening this side; red = weakening.\n\nThe canonical 'twin peaks' setup: in negative AO territory, two consecutive lows where the second is closer to zero than the first signals an exhaustion bottom (bullish 'twin peaks below zero'). Mirror inverted for tops.\n\nAO is part of Bill Williams' broader Chaos Trading system, which combines it with the Fractals, Alligator, and Accelerator/Decelerator. As a standalone momentum read, AO is fast (5/34 periods) and simple — good beginner-friendly oscillator.",
  description_hi:
    "AO conceptually 'momentum MACD' hai — fast aur slow SMA ka difference, zero line ke around histogram ki tarah plotted. MACD vs difference: AO 5/34 periods use karta (MACD ke 12/26 se kaafi shorter) aur close ke bajaye (high+low)/2 pe apply karta.\n\nZero line regime divider: AO > 0 = bullish momentum, AO < 0 = bearish. Har regime ke andar histogram bars ka colour immediate direction batata: green bar = is side momentum strengthen ho raha; red = weaken.\n\nCanonical 'twin peaks' setup: negative AO territory mein, do consecutive lows jahan second pehle se zero ke closer hai = exhaustion bottom (bullish 'twin peaks below zero'). Tops ke liye mirror inverted.\n\nAO Bill Williams ke broader Chaos Trading system ka part hai, jo isko Fractals, Alligator, aur Accelerator/Decelerator ke saath combine karta. Standalone momentum read ki tarah AO fast (5/34 periods) aur simple — accha beginner-friendly oscillator.",

  formula_explanation:
    "Midpoint = (high + low) / 2. AO = SMA(midpoint, 5) - SMA(midpoint, 34). Plotted as a histogram around zero. Bar colour: green if current AO > previous AO, red if current < previous. Default periods: 5 and 34 (no tuning).",

  default_period: 34,
  period_range: null,
  common_periods: [5, 34],

  use_cases: [
    {
      scenario: "Zero-line bias filter",
      what_to_do: "Long bias when AO > 0; short bias when AO < 0",
      why: "Single-condition bias filter that's faster than EMA-50 cross.",
    },
    {
      scenario: "Twin-peaks reversal entry",
      what_to_do: "In negative AO, watch for two consecutive lower-lows where the second is shallower — bullish reversal setup",
      why: "Pattern-based exhaustion signal. Tightly defined entry rule.",
    },
    {
      scenario: "Histogram colour shift",
      what_to_do: "Enter / exit on first colour change (green→red or red→green) after a sustained run",
      why: "Faster than MACD line crosses; useful for quick momentum-shift trades.",
    },
  ],

  common_signals: [
    {
      signal: "Zero-line cross up",
      condition: "AO crosses above 0",
      action: "Bullish regime — enable long-only strategies.",
    },
    {
      signal: "Twin peaks below zero",
      condition: "Two consecutive AO troughs in negative territory, second shallower than first",
      action: "Bullish reversal candidate.",
    },
    {
      signal: "Saucer (3-bar pattern)",
      condition: "In positive AO: red bar followed by smaller red bar followed by green bar",
      action: "Continuation long.",
    },
  ],

  pitfalls: [
    "Fixed 5/34 periods means AO can't be tuned for very fast or very slow timeframes — use a different oscillator if you need that.",
    "The twin-peaks pattern is somewhat subjective in real time; backtesting requires a precise definition of 'shallower'.",
    "On illiquid stocks, midpoint averaging produces gappy AO values.",
    "Less popular in Indian retail than RSI/MACD/Stochastic — community setup-sharing thin.",
  ],

  works_well_with: ["ema", "supertrend", "atr"],
  works_poorly_with: ["macd", "rsi", "stochastic"],

  example_strategies: [
    "AO Zero-Line Trend Filter (daily F&O)",
    "AO Twin Peaks Reversal (1h NIFTY)",
  ],

  indian_context:
    "AO is part of the Bill Williams toolkit that has small followings in Indian retail communities oriented around 'price-action + chaos' trading. AO's fast 5/34 periods make it more responsive than MACD on Indian intraday — useful for BANKNIFTY scalpers who want a momentum oscillator that updates within 1-2 bars rather than 5+.",
};
