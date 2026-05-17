import type { IndicatorContent } from "./_types";

export const HMA: IndicatorContent = {
  slug: "hma",
  name: "HMA (Hull Moving Average)",
  category: "trend",
  complexity: "advanced",

  one_liner_en:
    "WMA-based smoother that's dramatically smoother than SMA/EMA at equivalent reactivity. Modern preferred smooth MA.",
  one_liner_hi:
    "WMA-based smoother jo SMA/EMA se dramatically smoother hai equivalent reactivity pe. Modern preferred smooth MA.",

  description_en:
    "HMA (created by Alan Hull in 2005) builds on Weighted Moving Averages (WMAs) to produce a moving average that is both smoother and faster than EMA. The construction looks complex but the idea is elegant: subtract a slow WMA from a doubled fast WMA, then smooth the result with a WMA of sqrt(period) length.\n\nFormula: HMA(n) = WMA(2 × WMA(n/2) - WMA(n), sqrt(n)).\n\nVisually, HMA tracks trends very closely and shows almost no whipsaws during chop — far superior to EMA in this regard. The cost is more compute (three nested WMA passes) and a slightly steeper learning curve for the math.\n\nHMA's slope and colour are often used directly as trend signals: HMA sloping up + green = bullish trend; HMA sloping down + red = bearish. The `hull-ma-trend` template (already shipped in Phase 2-3) is built around this read.",
  description_hi:
    "HMA (Alan Hull ne 2005 mein banaya) Weighted Moving Averages (WMAs) pe build karta hai aisi moving average produce karne ke liye jo EMA se smoother aur faster dono ho. Construction complex lagta hai but idea elegant: slow WMA ko doubled fast WMA se subtract karo, phir result ko sqrt(period) length ki WMA se smooth karo.\n\nFormula: HMA(n) = WMA(2 × WMA(n/2) - WMA(n), sqrt(n)).\n\nVisually HMA trends ko bahut closely track karta aur chop mein almost zero whipsaws dikhata — EMA se kaafi superior is regard mein. Cost zyada compute (teen nested WMA passes) aur math ka thoda steep learning curve.\n\nHMA ka slope aur colour often direct trend signals ki tarah use hote: HMA sloping up + green = bullish trend; HMA sloping down + red = bearish. `hull-ma-trend` template (Phase 2-3 mein already shipped) is read ke around bana hai.",

  formula_explanation:
    "Compute WMA1 = WMA(close, period/2). Compute WMA2 = WMA(close, period). Intermediate = 2 × WMA1 - WMA2. HMA = WMA(intermediate, sqrt(period)). Round non-integer periods to nearest integer. Default period: 16.",

  default_period: 16,
  period_range: [4, 100],
  common_periods: [9, 16, 21, 55],

  use_cases: [
    {
      scenario: "Cleanest available trend line",
      what_to_do: "Replace EMA-50 with HMA-50 as the primary trend filter — fewer false flips, similar lag",
      why: "HMA's smoothness reduces whipsaw exit signals during normal pullbacks while still catching genuine trend reversals.",
    },
    {
      scenario: "Slope-colour visual bias",
      what_to_do: "Colour HMA green when slope is up, red when down — use that single visual as the bias filter",
      why: "Removes the mental overhead of comparing two MA lines; a single colour change is the trade trigger.",
    },
  ],

  common_signals: [
    {
      signal: "HMA colour flip",
      condition: "HMA slope flips from negative to positive (red → green)",
      action: "Long entry / cover short.",
    },
    {
      signal: "Price crosses HMA",
      condition: "Close crosses above HMA in a uptrend regime",
      action: "Continuation long after a pullback.",
    },
  ],

  pitfalls: [
    "Compute-heavy compared to EMA — three WMA passes instead of one. For high-frequency live computations, this matters.",
    "Rounding sqrt(period) to integer can shift HMA values slightly between platforms. Stay consistent.",
    "Despite the marketing, HMA isn't 'zero lag' — it lags less than EMA but still lags. Reversal confirmation is still 1-2 bars late.",
    "Some platforms use slightly different formulas (e.g. EHMA, THMA variants). Verify which version your library exports.",
  ],

  works_well_with: ["adx", "atr", "supertrend"],
  works_poorly_with: ["sma", "ema", "wma"],

  example_strategies: [
    "Hull MA Slope-Flip Trend (daily NIFTY-100 stocks) — see hull-ma-trend template",
    "HMA Crossover (15m NIFTY F&O)",
  ],

  indian_context:
    "HMA(21) on daily NIFTY F&O stocks is the smoothest single-MA trend filter available to Indian retail. Daily HMA flips are rare (~2-5 per quarter on individual large-caps) and meaningful. For intraday on BANKNIFTY, HMA-9 reacts fast enough to be useful — daily HMA on BANKNIFTY is too slow given its higher volatility regime shifts.",
};
