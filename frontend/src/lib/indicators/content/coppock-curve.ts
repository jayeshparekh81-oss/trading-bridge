import type { IndicatorContent } from "./_types";

export const COPPOCK_CURVE: IndicatorContent = {
  slug: "coppock-curve",
  name: "Coppock Curve",
  category: "momentum",
  complexity: "intermediate",

  one_liner_en:
    "A long-term momentum indicator built to spot major market bottoms — fires roughly once a market cycle.",
  one_liner_hi:
    "Long-term momentum indicator jo major market bottoms detect karne ke liye banaya — roughly market cycle mein ek baar fire karta.",

  description_en:
    "The Coppock Curve was designed by Edwin Coppock in 1962 for finding major MARKET BOTTOMS — not entries, not signals every week, but the kind of multi-year buying opportunities that show up once a cycle. The classic use: when Coppock turns up from a negative reading, it's a buy signal for long-term investors.\n\nThe construction reflects its purpose. It uses 14-month and 11-month rate-of-change values summed, then weighted-MA smoothed over 10 months. The long lookback periods filter out noise — short-term swings barely move the curve. That's the point: this indicator ignores weekly news and focuses on the underlying multi-quarter momentum cycle.\n\nApplied to NIFTY's monthly chart since 2000, Coppock signals have caught the 2003 post-crash bottom, the 2009 bottom, and the 2020 COVID bottom. It also gave false signals around 2013 and 2018 — no indicator is perfect at calling bottoms, but the win rate for major reversal-from-negative is meaningful.\n\nFor short-term traders, this indicator is largely useless — it's calibrated for monthly data and multi-year horizons. For long-term investors building a positional book in Indian equities, it's a structural compass.",
  description_hi:
    "Coppock Curve Edwin Coppock ne 1962 mein banaya major MARKET BOTTOMS dhundhne ke liye — entries nahi, har hafte ke signals nahi, but jo multi-year buying opportunities ek cycle mein ek baar aati. Classic use: jab Coppock negative reading se up turn kare, long-term investors ke liye buy signal.\n\nConstruction iske purpose ko reflect karta. 14-month aur 11-month rate-of-change values sum karke, phir 10-month weighted-MA smoothing. Long lookback periods noise filter karte — short-term swings curve ko barely move karte. Yahi point hai: ye indicator weekly news ignore karta aur underlying multi-quarter momentum cycle pe focus karta.\n\nNIFTY ke monthly chart pe 2000 se applied, Coppock signals 2003 post-crash bottom, 2009 bottom, aur 2020 COVID bottom catch kiye. 2013 aur 2018 ke around false signals bhi diye — koi indicator perfect bottom-caller nahi, but negative-se-reversal ka win rate meaningful hai.\n\nShort-term traders ke liye ye indicator zyaadatar useless hai — monthly data aur multi-year horizons ke liye calibrated hai. Indian equities mein positional book banane wale long-term investors ke liye structural compass hai.",

  formula_explanation:
    "Step 1: Compute 14-month and 11-month Rate of Change of monthly close prices. ROC_n = (Close_today / Close_n_months_ago - 1) × 100. Step 2: Add the two ROCs together. Step 3: Apply a 10-period weighted moving average to the summed series. Output: a slow-moving curve oscillating around zero. The asymmetric ROC periods (14 + 11) come from Coppock's original work on grief cycles — odd origin but the math endures.",

  default_period: 10,
  period_range: [6, 14],
  common_periods: [10],

  use_cases: [
    {
      scenario: "Identifying major market bottoms for long-term equity entries",
      what_to_do: "Wait for Coppock to be negative, then enter long when it turns up",
      why: "Negative-to-up transitions historically align with multi-year buying opportunities — high conviction, low frequency.",
    },
    {
      scenario: "Validating that a 'bottom' is real and not a dead-cat bounce",
      what_to_do: "If Coppock has NOT turned up yet, treat the bounce as a counter-trend rally — don't add aggressively",
      why: "Short-term bounces happen all the time; Coppock only fires when the multi-quarter momentum has actually shifted.",
    },
    {
      scenario: "Long-term portfolio risk-on/risk-off positioning",
      what_to_do: "When Coppock is positive and rising, hold equity exposure; when it turns down from a high, trim",
      why: "Macro-cycle awareness for an investor who doesn't want to time every news event but does want to be on the right side of multi-year trends.",
    },
  ],

  common_signals: [
    {
      signal: "Major buy signal",
      condition: "Coppock turns up from a negative value",
      action: "Multi-year long entry candidate — scale in over several months.",
    },
    {
      signal: "Late-cycle warning",
      condition: "Coppock has been positive and rising for 18+ months, then flattens",
      action: "Reduce risk exposure; positive but flat is the warning, not the trigger.",
    },
    {
      signal: "Continued strength",
      condition: "Coppock rising through a positive value",
      action: "No new action — continue holding existing longs.",
    },
  ],

  pitfalls: [
    "Useless on intraday or daily charts — Coppock is calibrated for monthly bars and multi-year cycles.",
    "Long lookback means signals fire AFTER the actual bottom — you'll miss the first 10-20% of the recovery rally.",
    "False signals happen — 2013 NIFTY case is a known counterexample. Always pair with macro context.",
    "Don't fit other timeframes by shortening periods — the indicator's math doesn't translate cleanly to daily.",
    "Coppock identifies BOTTOMS only — it doesn't have a symmetric 'top' signal; use other tools for tops.",
  ],

  works_well_with: ["macd", "rsi", "ema"],
  works_poorly_with: ["roc", "momentum", "tsi"],

  example_strategies: [
    "Coppock long-term entry on NIFTY monthly (positional investing)",
    "Index fund SIP boost-up signal for risk-on quarters",
    "Multi-year portfolio rebalance trigger",
  ],

  indian_context:
    "On NIFTY monthly data, Coppock has called bottoms in 2003 (post-tech bust), 2009 (post-GFC), and April 2020 (post-COVID crash). 2013 produced a false signal that resolved positively only 2 years later. For Indian retail investors who do positional SIPs in index funds, watching Coppock on NIFTY monthly is the closest thing to a 'when to be aggressive' compass. Avoid using on individual stocks — Coppock was designed for indices with sufficient data depth and broad-market representation.",
};
