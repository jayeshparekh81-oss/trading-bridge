import type { IndicatorContent } from "./_types";

export const ACCUMULATION_DISTRIBUTION: IndicatorContent = {
  slug: "accumulation-distribution",
  name: "Accumulation/Distribution Line (A/D)",
  category: "volume",
  complexity: "intermediate",

  one_liner_en:
    "Cumulative volume-flow indicator — rising A/D shows accumulation (smart money buying); falling shows distribution (smart money selling).",
  one_liner_hi:
    "Cumulative volume-flow indicator — rising A/D accumulation (smart money buying) dikhata; falling distribution (smart money selling).",

  description_en:
    "The Accumulation/Distribution Line (A/D, sometimes ADL) was created by Marc Chaikin to track the relationship between price and volume — specifically, whether volume is happening on up-moves (accumulation) or down-moves (distribution). The cumulative nature is important: each bar's contribution adds to the running total.\n\nThe bar-by-bar contribution depends on where the close lands within the bar's range. A close near the high of the bar adds positive volume to A/D (accumulators winning). A close near the low subtracts volume (distributors winning). A close at the midpoint contributes zero.\n\nA/D's most-cited use is divergence: when price rises but A/D fails to rise alongside, the rally lacks volume support — distribution is happening even as price drifts up. This is one of the earliest reliable signs of an upcoming reversal. The reverse (price falling, A/D rising) signals bullish accumulation under apparent weakness.\n\nFor Indian retail, A/D works best on cash-equity F&O stocks where volume meaningfully represents institutional participation. On index futures, A/D is muddled by hedging flows that don't reflect directional sentiment.",
  description_hi:
    "Accumulation/Distribution Line (A/D, kabhi ADL) Marc Chaikin ne banaya price aur volume ke relationship ko track karne ke liye — specifically, volume up-moves pe ho raha (accumulation) ya down-moves pe (distribution). Cumulative nature important hai: har bar ka contribution running total mein add hota.\n\nBar-by-bar contribution depend karta bar ke range mein close kahaan land karta hai. Bar ke high ke paas close A/D mein positive volume add karta (accumulators winning). Low ke paas close volume subtract karta (distributors winning). Midpoint pe close zero contribute karta.\n\nA/D ka most-cited use divergence hai: jab price rise ho but A/D alongside rise na kare, rally mein volume support nahi — distribution ho rahi apparent up-drift ke baawjood. Ye upcoming reversal ke earliest reliable signs mein se ek hai. Reverse (price falling, A/D rising) bullish accumulation signal hai apparent weakness mein.\n\nIndian retail ke liye A/D cash-equity F&O stocks pe best kaam karta jahan volume meaningfully institutional participation ko represent karta. Index futures pe A/D hedging flows se muddled hota jo directional sentiment reflect nahi karte.",

  formula_explanation:
    "Step 1: Money Flow Multiplier (MFM) = ((Close - Low) - (High - Close)) / (High - Low). Range: -1 to +1. Step 2: Money Flow Volume (MFV) = MFM × Volume. Step 3: A/D[today] = A/D[yesterday] + MFV[today]. Running cumulative sum. No period parameter — A/D is path-dependent from inception.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Divergence at major price levels for reversal trades",
      what_to_do: "Price prints higher high but A/D prints lower high = bearish divergence; reverse for bullish",
      why: "Volume-based divergence at structural levels (52-week highs, prior swing points) catches reversals that pure price action misses.",
    },
    {
      scenario: "Confirming or rejecting a breakout",
      what_to_do: "Breakouts where A/D rises strongly alongside are higher-conviction; flat A/D during breakout = likely fake-out",
      why: "Real breakouts attract volume; pure price-momentum breakouts without volume support tend to reverse within days.",
    },
    {
      scenario: "Identifying smart-money positioning during consolidation",
      what_to_do: "During flat consolidation, watch A/D direction — rising = accumulation phase before move up; falling = distribution before move down",
      why: "A/D can reveal positioning even when price is sideways; this is its most underrated use.",
    },
  ],

  common_signals: [
    {
      signal: "Bearish divergence",
      condition: "Price higher high, A/D lower high",
      action: "Tighten longs / consider short; underlying volume is selling.",
    },
    {
      signal: "Bullish divergence",
      condition: "Price lower low, A/D higher low",
      action: "Long entry candidate; accumulation is occurring under apparent weakness.",
    },
    {
      signal: "Confirmed breakout",
      condition: "Price breaks resistance AND A/D simultaneously breaks above prior high",
      action: "High-conviction long; both price and volume confirm.",
    },
    {
      signal: "Accumulation in consolidation",
      condition: "Price sideways but A/D trending up",
      action: "Bullish positional setup forming; prepare for breakout long.",
    },
  ],

  pitfalls: [
    "A/D is cumulative — absolute value is meaningless; only direction and divergence matter.",
    "Gap-heavy stocks distort the Money Flow Multiplier — the formula assumes continuous trading.",
    "On index futures with hedging volume, A/D signals get muddled; cash equity is its native habitat.",
    "Divergence can persist for many bars before resolving — divergence is a heads-up, not a precise entry trigger.",
    "Don't compare A/D values across different stocks; only its trend within a single stock is informative.",
  ],

  works_well_with: ["obv", "mfi", "supports-resistances", "fibonacci-retracement"],
  works_poorly_with: ["volume-profile"],

  example_strategies: [
    "A/D divergence trader on F&O cash equities (daily)",
    "A/D-confirmed breakout strategy (swing trading)",
    "Pre-breakout accumulation scanner across NIFTY 100",
  ],

  indian_context:
    "A/D on NIFTY F&O cash equities works particularly well on RIL, HDFC Bank, ICICI Bank, and TCS where institutional volume dominates and the indicator's volume-flow read is meaningful. During FII outflow weeks, A/D often turns negative across large-caps even as price holds — a useful early-warning framing. Avoid on index futures (NIFTY/BANKNIFTY) where hedging flows distort the signal. For mid-cap F&O, A/D can flag sector-rotation accumulation ahead of price during themes like renewables, defense, or PSU re-rating cycles — confirm on your own data before sizing positions on the signal alone. Compare A/D across sector pairs (banking vs IT) for relative-strength rotation cues.",
};
