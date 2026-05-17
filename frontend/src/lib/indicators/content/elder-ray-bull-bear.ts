import type { IndicatorContent } from "./_types";

export const ELDER_RAY_BULL_BEAR: IndicatorContent = {
  slug: "elder-ray-bull-bear",
  name: "Elder-Ray Bull/Bear Power",
  category: "momentum",
  complexity: "intermediate",

  one_liner_en:
    "Two oscillators that measure bull power (high above EMA) and bear power (low below EMA) — useful for timing entries within a trend.",
  one_liner_hi:
    "Do oscillators jo bull power (high EMA ke upar) aur bear power (low EMA ke neeche) measure karte — trend ke andar entries time karne ke liye useful.",

  description_en:
    "Dr. Alexander Elder created Elder-Ray to separately measure the strength of bulls (buyers) and bears (sellers) in any market session. The concept is elegant: take a 13-period EMA as the 'consensus' price for the period. Bull Power is the day's High minus this EMA — measures how far above consensus bulls pushed price intraday. Bear Power is the day's Low minus the EMA — measures how far below consensus bears pushed it.\n\nElder's trading philosophy: trade WITH the trend (defined by a longer EMA), but TIME entries using bull/bear power readings within that trend. Specifically — in an uptrend, buy when Bear Power is negative but rising (bears losing strength). In a downtrend, short when Bull Power is positive but falling (bulls losing strength).\n\nThe asymmetric trading rule — using bear power for long entries and bull power for short entries — feels counterintuitive but reflects Elder's insight: the time to enter a long isn't when bulls are strongest, it's when bears are weakest.\n\nFor Indian retail, Elder-Ray on NIFTY F&O daily provides excellent intra-trend entry timing. The dual reading also gives a clearer 'trend exhaustion' signal than single oscillators.",
  description_hi:
    "Dr. Alexander Elder ne Elder-Ray banaya bulls (buyers) aur bears (sellers) ki strength alag-alag measure karne ke liye kisi bhi market session mein. Concept elegant hai: 13-period EMA ko period ke liye 'consensus' price lo. Bull Power = day ka High minus ye EMA — measure karta bulls ne intraday price ko consensus ke kitna upar push kiya. Bear Power = day ka Low minus EMA — measure karta bears ne kitna neeche push kiya.\n\nElder ki trading philosophy: trend ke saath trade karo (longer EMA se defined), but bull/bear power readings se entries TIME karo us trend ke andar. Specifically — uptrend mein, jab Bear Power negative but rising ho (bears strength khote ja rahe) tab buy. Downtrend mein, jab Bull Power positive but falling ho (bulls strength khote ja rahe) tab short.\n\nAsymmetric trading rule — long entries ke liye bear power use karna aur short entries ke liye bull power — counterintuitive lagta but Elder ka insight reflect karta: long enter karne ka time wo nahi jab bulls strongest ho, wo hai jab bears weakest ho.\n\nIndian retail ke liye Elder-Ray NIFTY F&O daily pe excellent intra-trend entry timing deta. Dual reading single oscillators se 'trend exhaustion' bhi cleaner signal karta.",

  formula_explanation:
    "Step 1: Compute 13-period EMA of close (Elder's recommended trend filter). Step 2: Bull Power = High - EMA. Step 3: Bear Power = Low - EMA. Both plot as histograms above and below a zero line. In Elder's broader Triple Screen system, the 13-EMA is replaced with longer EMAs depending on timeframe alignment, but 13 is the standard for daily charts.",

  default_period: 13,
  period_range: [8, 26],
  common_periods: [13, 21],

  use_cases: [
    {
      scenario: "Long entry timing within an established uptrend",
      what_to_do: "In an uptrend, enter long when Bear Power is negative but rising (returning toward zero)",
      why: "Bear weakness during an uptrend is the best long entry — better than waiting for bull strength which often signals exhaustion.",
    },
    {
      scenario: "Short entry timing within an established downtrend",
      what_to_do: "In a downtrend, enter short when Bull Power is positive but falling (returning toward zero)",
      why: "Bull weakness during a downtrend is the best short entry; mirror of the long rule.",
    },
    {
      scenario: "Trend exhaustion detection",
      what_to_do: "When Bull Power and Bear Power both shrink toward zero, the trend is losing energy — prepare for consolidation or reversal",
      why: "Dual-shrinking is a stronger exhaustion signal than single-oscillator exhaustion because it confirms both sides are tired.",
    },
  ],

  common_signals: [
    {
      signal: "Long entry (Elder rule)",
      condition: "Bear Power negative but rising, in established uptrend",
      action: "Long entry candidate with bears weakening.",
    },
    {
      signal: "Short entry (Elder rule)",
      condition: "Bull Power positive but falling, in established downtrend",
      action: "Short entry candidate with bulls weakening.",
    },
    {
      signal: "Bullish divergence",
      condition: "Price lower low, Bear Power higher low (less negative)",
      action: "Bullish reversal candidate; bears running out of strength.",
    },
    {
      signal: "Trend exhaustion",
      condition: "Both Bull Power and Bear Power shrinking toward zero",
      action: "Consolidation or reversal incoming — tighten stops.",
    },
  ],

  pitfalls: [
    "The asymmetric entry rule (bear power for longs) trips up new users — practice paper trading until it's natural.",
    "Elder's rule requires PRE-DETERMINED trend direction; using Elder-Ray without a trend filter produces poor signals.",
    "On intraday timeframes, the 13-EMA is too short — recalibrate or use Elder's Triple Screen methodology.",
    "False divergences common in low-volume periods (lunch hour, holiday weeks).",
    "Don't pair with another EMA-based indicator — they'll be highly correlated.",
  ],

  works_well_with: ["adx", "ema", "supports-resistances", "rsi"],
  works_poorly_with: ["macd", "wma"],

  example_strategies: [
    "Elder Triple Screen on NIFTY F&O daily",
    "Bull/Bear Power divergence trader on swing setups",
    "Trend exhaustion overlay on EMA-based positional longs",
  ],

  indian_context:
    "Elder-Ray on NIFTY daily during sustained trends (e.g., 2023 H2 rally) provides excellent intra-trend long entry timing — Bear Power readings dipping below zero and rising back have historically marked the best dip-buying moments. On BANKNIFTY (higher beta), the absolute values of Bull/Bear Power are larger; use relative-percentage comparisons rather than absolute thresholds. For F&O cash equities, Elder-Ray is most useful on RIL, HDFC Bank, INFY in trending phases. Avoid using on indices around major event weeks (budget, RBI policy) where Bull/Bear Power readings spike from sentiment rather than positioning.",
};
