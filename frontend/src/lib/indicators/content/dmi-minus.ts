import type { IndicatorContent } from "./_types";

export const DMI_MINUS: IndicatorContent = {
  slug: "dmi-minus",
  name: "DI- (Directional Indicator Minus)",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "Measures downward directional movement strength. Mirror of DI+ in Wilder's DMI pair.",
  one_liner_hi:
    "Downward directional movement strength measure karta. Wilder ke DMI pair mein DI+ ka mirror.",

  description_en:
    "DI- isolates the downward component of price movement. Each bar measures how much the low dropped below the prior low — only when that drop was greater than the corresponding high-to-high rise. The result is smoothed (Wilder's average) and normalised against ATR to produce DI-, on a 0-100 scale.\n\nLike DI+, DI- rarely trades alone. It pairs with DI+ (bullish counterpart) and ADX (combined trend strength). When DI- is above DI+, bears are in control; the steeper the gap, the stronger the downtrend.\n\nThe canonical short signal is DI- crossing above DI- — but unfiltered crosses are noisy. Pair with ADX > 25 to gate the signal to actual trend regimes.",
  description_hi:
    "DI- price movement ka downward component isolate karta. Har bar pe measure karta low ne previous low ko kitna drop kiya — sirf jab woh drop corresponding high-to-high rise se zyada thi. Result smoothed hoti (Wilder ki average) aur ATR ke against normalised, 0-100 scale pe.\n\nDI+ ki tarah, DI- akele rarely trade hota. DI+ (bullish counterpart) aur ADX (combined trend strength) ke saath paired. DI- DI+ ke upar = bears control mein; gap jitna steep, downtrend utna strong.\n\nCanonical short signal DI- crossing above DI+ hai — but unfiltered noisy. ADX > 25 ke saath gate karo actual trend regimes ke liye.",

  formula_explanation:
    "-DM = prev_low - low if (prev_low - low) > (high - prev_high) AND > 0, else 0. Smoothed over `period` via Wilder's average. DI- = 100 × smoothed_-DM / smoothed_TR. Default period: 14.",

  default_period: 14,
  period_range: [5, 50],
  common_periods: [10, 14, 20],

  use_cases: [
    {
      scenario: "Short / exit-long trigger in downtrending markets",
      what_to_do: "Short or exit longs when DI- crosses above DI+ AND ADX > 25",
      why: "Combination ensures direction (DI- ahead) + strength (ADX confirms a trend exists). Single-condition is unreliable.",
    },
    {
      scenario: "Sector weakness detector",
      what_to_do: "On sector indices, DI- > DI+ for sustained periods signals sector outflows",
      why: "Useful as 'avoid this sector' filter before stock-level screens; the macro picture often shows up in DMI before individual stock prices fully roll over.",
    },
  ],

  common_signals: [
    {
      signal: "Bearish DI cross",
      condition: "DI- crosses above DI+",
      action: "Short / exit-long candidate; confirm with ADX > 20.",
    },
    {
      signal: "DI- pull-away",
      condition: "DI- extending higher while DI+ falls",
      action: "Downtrend strengthening — hold shorts.",
    },
  ],

  pitfalls: [
    "DI- crosses without ADX confirmation are notoriously noisy.",
    "DI- pinned high during prolonged downtrends; don't fade extended downward extremes.",
    "Short selling has its own constraints in Indian cash equity (SLB margin, T+1 buyback rule on certain securities) — DI- signals alone don't account for that.",
    "Default period 14 lags. Shorter periods are twitchy.",
  ],

  works_well_with: ["adx", "dmi", "ema", "supertrend"],
  works_poorly_with: ["rsi", "stochastic"],

  example_strategies: [
    "DI- Short with ADX Filter (daily F&O stocks)",
    "Sector Weakness Filter for Long-Only Portfolios",
  ],

  indian_context:
    "DI- on weekly NIFTY sector indices catches multi-week sector outflows reliably. For Indian retail, DI- is more useful as a 'don't go long' signal than as a short-entry signal — Indian cash equity short-selling is harder than overseas, and most retail traders use DI- to time exits rather than initiate shorts.",
};
