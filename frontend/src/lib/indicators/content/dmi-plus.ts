import type { IndicatorContent } from "./_types";

export const DMI_PLUS: IndicatorContent = {
  slug: "dmi-plus",
  name: "DI+ (Directional Indicator Plus)",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "Measures upward directional movement strength. Half of Wilder's DMI pair (with DI-).",
  one_liner_hi:
    "Upward directional movement strength measure karta. Wilder ke DMI pair ka aadha (DI- ke saath).",

  description_en:
    "DI+ (Directional Indicator Plus) isolates the upward component of price movement. Each bar, the indicator measures how much the high exceeded the prior high — only when that exceedance was also greater than the corresponding low-to-low drop. The resulting 'plus directional movement' is smoothed (Wilder's recursive average) and divided by the average true range to produce DI+, normalised 0-100.\n\nDI+ is rarely used standalone. It pairs with DI- (the mirror calculation for downward movement) and ADX (which uses both) in the textbook DMI triplet. The interpretation: DI+ above DI- means bulls are in control; DI+ rising while DI- falls means the upside trend is strengthening.\n\nThe DI+ vs DI- 'gap' (their absolute difference) feeds the ADX calculation — so DI+/DI- both being far apart and stable produces high ADX (strong trend); both being close and crossing rapidly produces low ADX (chop).\n\nAs an entry trigger, DI+ crossing above DI- is the classical 'bullish' signal — but on its own it's noisy. Pair with ADX > 25 to filter chop-induced crosses.",
  description_hi:
    "DI+ (Directional Indicator Plus) price movement ka upward component isolate karta hai. Har bar pe indicator measure karta hai high ne previous high ko kitna exceed kiya — sirf jab woh exceedance corresponding low-to-low drop se zyada thi. Resulting 'plus directional movement' smoothed hoti hai (Wilder ki recursive average) aur average true range se divide hoti hai DI+ produce karne ke liye, 0-100 mein normalised.\n\nDI+ rarely standalone use hota. DI- (downward movement ki mirror calculation) aur ADX (jo dono use karta) ke saath textbook DMI triplet mein paired. Interpretation: DI+ DI- ke upar = bulls control mein; DI+ rising while DI- falling = upside trend strengthen ho rahi.\n\nDI+ vs DI- 'gap' (unka absolute difference) ADX calculation feed karta hai — DI+/DI- dono far apart aur stable = high ADX (strong trend); dono close aur rapidly crossing = low ADX (chop).\n\nEntry trigger ki tarah DI+ crossing above DI- classical 'bullish' signal hai — par akele noisy. ADX > 25 ke saath pair karo chop-crosses filter karne ke liye.",

  formula_explanation:
    "+DM = high - prev_high if (high - prev_high) > (prev_low - low) AND > 0, else 0. Smoothed over `period` via Wilder's average. DI+ = 100 × smoothed_+DM / smoothed_TR (where TR is the True Range). Default period: 14.",

  default_period: 14,
  period_range: [5, 50],
  common_periods: [10, 14, 20],

  use_cases: [
    {
      scenario: "Trend-direction filter when paired with ADX",
      what_to_do: "Long bias only when DI+ > DI- AND ADX > 25",
      why: "Direction (DI+ ahead) + strength (ADX high) = quality trend regime. One condition without the other is unreliable.",
    },
    {
      scenario: "Sector rotation trigger",
      what_to_do: "Watch sector indices for fresh DI+ crosses above DI- — a sign of rotation INTO the sector",
      why: "Money flowing into a sector first shows up as a directional regime change in DMI before price magnitude becomes obvious.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish DI cross",
      condition: "DI+ crosses above DI-",
      action: "Long bias candidate; confirm with ADX > 20.",
    },
    {
      signal: "DI+ pull-away",
      condition: "DI+ extending higher while DI- falls",
      action: "Trend strengthening — hold longs.",
    },
  ],

  pitfalls: [
    "DI+ crosses without ADX confirmation are notoriously noisy. The 'DI crossover strategy without ADX' is a classic beginner mistake.",
    "Both DI+ and DI- can be flat and crossing near each other in chop — those crosses mean nothing.",
    "DI+ alone tells you nothing about magnitude — pair with price or volume for trade sizing.",
    "Default period 14 lags. Shorter periods amplify noise.",
  ],

  works_well_with: ["adx", "dmi", "ema", "supertrend"],
  works_poorly_with: ["rsi", "stochastic"],

  example_strategies: [
    "DI+ Cross + ADX Filter (daily NIFTY F&O stocks)",
    "Sector Rotation via DI+ (weekly NIFTY sub-indices)",
  ],

  indian_context:
    "DI+ on weekly NIFTY sector indices (NIFTY IT, METAL, BANK, etc.) is one of the cleaner sector-rotation read-outs available to Indian retail. When DI+ crosses above DI- on a sector index AND ADX is rising, capital is rotating into that sector — heavyweight stocks usually follow within 2-3 sessions. Less differentiated from DI- on broad indices because aggregation balances directional moves.",
};
