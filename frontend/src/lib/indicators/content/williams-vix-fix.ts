import type { IndicatorContent } from "./_types";

export const WILLIAMS_VIX_FIX: IndicatorContent = {
  slug: "williams-vix-fix",
  name: "Williams VIX Fix (WVF)",
  category: "volatility",
  complexity: "advanced",

  one_liner_en:
    "Synthetic VIX-like measure for any instrument — spikes mark capitulation bottoms and high-conviction long entries.",
  one_liner_hi:
    "Kisi bhi instrument ke liye synthetic VIX-like measure — spikes capitulation bottoms aur high-conviction long entries mark karte.",

  description_en:
    "Larry Williams designed the Williams VIX Fix to approximate VIX-like volatility readings using only price data — useful for individual stocks where no native volatility index exists. The original VIX is calculated from options pricing on the underlying index. WVF gets close to VIX behavior with only OHLC of the instrument itself.\n\nThe formula reads recent highest highs and current lows to estimate range-driven fear. When WVF spikes higher, it means price has plunged sharply relative to recent highs — the textbook 'capitulation' pattern. Like VIX, WVF SPIKES typically mark BOTTOMS, not tops; fear peaks at the bottom of moves.\n\nWilliams' suggested trade: when WVF exceeds its own upper Bollinger Band AND is in its top 90th percentile over the last 50 bars, that's a capitulation buy signal. Historically these signals catch the best long entries near market lows.\n\nFor Indian retail, WVF is invaluable on individual F&O stocks — NIFTY has India VIX but RIL or HDFC Bank don't have native vol indices. WVF on these stocks gives a fear-based bottom signal that's not available otherwise.",
  description_hi:
    "Larry Williams ne Williams VIX Fix design kiya VIX-like volatility readings sirf price data se approximate karne ke liye — individual stocks ke liye useful jahan native volatility index nahi hota. Original VIX underlying index ke options pricing se calculate hota. WVF instrument ke OHLC se hi VIX behavior ke close pohnchta.\n\nFormula recent highest highs aur current lows read karke range-driven fear estimate karta. Jab WVF higher spike kare, matlab recent highs ke against price sharply plunged — textbook 'capitulation' pattern. VIX ki tarah, WVF SPIKES typically BOTTOMS mark karte, tops nahi; fear moves ke bottom pe peak hota.\n\nWilliams ka suggested trade: jab WVF apni upper Bollinger Band exceed kare AND last 50 bars mein top 90th percentile mein ho, wo capitulation buy signal hai. Historically ye signals market lows ke best long entries catch karte.\n\nIndian retail ke liye WVF individual F&O stocks pe invaluable hai — NIFTY ka India VIX hai but RIL ya HDFC Bank ka native vol index nahi. In stocks pe WVF fear-based bottom signal deta jo otherwise available nahi hota.",

  formula_explanation:
    "WVF = ((Highest_high[22] - Low[today]) / Highest_high[22]) × 100. Apply a 20-period Bollinger Band around WVF (top band at +2 std dev). Signal fires when WVF closes above the upper BB AND is at a 50-bar percentile rank ≥ 0.9. The 22 and 20 periods are Williams' defaults; some traders use 28/20.",

  default_period: 22,
  period_range: [15, 30],
  common_periods: [22],

  use_cases: [
    {
      scenario: "Catching capitulation bottoms on individual F&O stocks",
      what_to_do: "WVF spike above upper BB + top 10% percentile = high-conviction long entry",
      why: "Fear-driven capitulations historically have the highest reward-to-risk for swing long entries.",
    },
    {
      scenario: "Distinguishing real bottoms from corrections",
      what_to_do: "Compare WVF to its recent percentile — moderate readings = correction, extreme readings = capitulation",
      why: "Not every dip is a bottom; WVF percentile separates buyable fear from healthy pullbacks.",
    },
    {
      scenario: "Confirming reversal candle setups",
      what_to_do: "If a hammer / engulfing pattern coincides with a WVF capitulation signal, conviction multiplies",
      why: "Pattern + WVF + percentile confluence is one of the strongest mean-reversion setups in retail trading.",
    },
  ],

  common_signals: [
    {
      signal: "Capitulation buy signal",
      condition: "WVF above upper Bollinger Band AND WVF percentile ≥ 90% over last 50 bars",
      action: "Strong long entry candidate; wait for next-bar bullish confirmation.",
    },
    {
      signal: "Moderate fear reading",
      condition: "WVF 60-80 percentile over last 50 bars",
      action: "Pullback but not capitulation — buy on confirmed support test, not aggressively.",
    },
    {
      signal: "Calm market",
      condition: "WVF below 30 percentile for sustained periods",
      action: "No fear-based entries; market is trending or boring — use different setups.",
    },
  ],

  pitfalls: [
    "WVF is NOT a top indicator — it doesn't symmetrically signal market tops the way bottoms.",
    "Sustained downtrends keep WVF elevated; signals fire late if the move continues without true capitulation.",
    "Default 22-period assumes daily charts — recalibrate for weekly or intraday timeframes.",
    "Around earnings releases, WVF spikes from gap moves rather than real capitulation — filter by news context.",
    "Williams' specific 0.9 percentile threshold is well-tested but not universal; some traders use 0.85.",
  ],

  works_well_with: ["bollinger-bands", "rsi", "atr", "supports-resistances"],
  works_poorly_with: ["standard-deviation", "keltner-channel"],

  example_strategies: [
    "WVF capitulation buy on F&O stocks (daily)",
    "WVF + hammer reversal confluence (swing trading)",
    "Pre-earnings WVF screening for buyable dips",
  ],

  indian_context:
    "On NIFTY F&O stocks, WVF is positioned to flag deep capitulation moments — back-test on your own selection of past macro/event shocks to validate that the upper-band + percentile rule produces useful long-side entries on the names you trade. BANKNIFTY shows WVF spikes more frequently due to higher beta — apply stricter percentile filters (95% rather than 90%) to avoid false signals. For mid-cap F&O stocks, WVF's capitulation framing is appealing because mid-caps tend to over-shoot on fear, but signal quality varies stock-by-stock. Avoid using WVF on illiquid small-caps where range readings get distorted by single trades.",
};
