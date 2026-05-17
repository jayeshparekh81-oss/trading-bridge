import type { IndicatorContent } from "./_types";

export const PARABOLIC_SAR: IndicatorContent = {
  slug: "parabolic-sar",
  name: "Parabolic SAR (Stop and Reverse)",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "Dots above or below price that flip on every trend reversal. Acts as both stop-loss and reversal signal.",
  one_liner_hi:
    "Price ke upar ya neeche dots jo har trend reversal pe flip karte hain. Stop-loss aur reversal signal dono ki tarah kaam karte hain.",

  description_en:
    "Parabolic SAR (developed by J. Welles Wilder, same author as RSI and ATR) plots a single dot per bar — below price in uptrends, above price in downtrends. Each new bar moves the dot closer to price by an 'acceleration factor' that increases each time price prints a new extreme in the current trend. Eventually the dot catches price and the indicator flips: stop AND reverse — exit the long, enter the short (or vice versa).\n\nThe key parameters are the starting acceleration (default 0.02), the increment per new extreme (default 0.02), and the maximum acceleration (default 0.2). Larger values make the SAR tighten faster — sooner flips, smaller stops. Smaller values give the trend more breathing room.\n\nSAR's promise is that it's always in the market. It never sits out — it's either long or short. That's great in trending markets and terrible in sideways markets. Beginners often use it as the only signal generator; that's wrong. The standard pro recipe is to use SAR purely as a trailing stop ONLY when an independent trend filter says we're in a trend.",
  description_hi:
    "Parabolic SAR (J. Welles Wilder ne banaya, RSI aur ATR ka bhi same author) har bar pe ek dot plot karta — uptrends mein price ke neeche, downtrends mein price ke upar. Har naya bar dot ko price ke paas le aata 'acceleration factor' se jo har baar badhta hai jab price current trend mein naya extreme print kare. Eventually dot price ko catch karta hai aur indicator flip ho jaata: stop AND reverse — long exit, short entry (ya ulta).\n\nKey parameters: starting acceleration (default 0.02), increment per new extreme (default 0.02), aur maximum acceleration (default 0.2). Bade values SAR ko fast tighten karte — earlier flips, smaller stops. Chhote values trend ko zyada breathing room dete.\n\nSAR ka promise hai always in market. Kabhi out nahi baithta — long ya short. Trending markets mein great aur sideways mein terrible. Beginners often only signal generator ki tarah use karte hain; galat hai. Standard pro recipe: SAR ko sirf trailing stop ki tarah use karo, AND only when independent trend filter trend confirm kare.",

  formula_explanation:
    "SAR(today) = SAR(yesterday) + AF × (EP - SAR(yesterday)), where EP is the extreme price (highest high in uptrend, lowest low in downtrend) and AF is the acceleration factor. AF starts at 0.02, increments by 0.02 each time a new EP is set, caps at 0.2. When price crosses SAR, the indicator flips and SAR resets to the prior EP.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Trailing stop in confirmed trends",
      what_to_do: "Use SAR as the trailing stop ONLY when a 50-EMA / Supertrend / ADX > 25 confirms a trend",
      why: "Without a trend filter, SAR will flip-and-lose constantly in chop. With a filter, it's a high-quality volatility-aware trail.",
    },
    {
      scenario: "Quick visual trend reversal indicator",
      what_to_do: "Glance at the chart — dots above price = trending down, dots below = trending up",
      why: "Fast visual heuristic for chart pattern recognition before zooming in on details.",
    },
  ],

  common_signals: [
    {
      signal: "SAR flip up",
      condition: "Dot moves from above price to below price",
      action: "Bullish reversal — long entry candidate (with trend filter).",
    },
    {
      signal: "SAR flip down",
      condition: "Dot moves from below price to above price",
      action: "Bearish reversal — long exit / short entry candidate.",
    },
    {
      signal: "SAR riding under price",
      condition: "Dots stay below price for many bars, gradually tightening",
      action: "Trend strength — hold position, use SAR as trailing stop.",
    },
  ],

  pitfalls: [
    "Designed for trends. In choppy markets it generates losses through repeated flip-and-reverse cycles. Always pair with a trend filter.",
    "The 'stop and reverse' default means you flip from long to short on the same bar. In Indian markets that may mean an immediate F&O entry on the new side — slippage matters.",
    "Default 0.02 acceleration is conservative. Aggressive traders use 0.03-0.05 for faster reaction at the cost of more whipsaws.",
    "SAR doesn't anticipate trends — it only locks in to existing ones. First bar of a new trend, SAR is still pointing the wrong way.",
    "Different libraries handle the initial bar slightly differently. Verify yours matches your charting tool before going live.",
  ],

  works_well_with: ["ema", "adx", "supertrend", "atr"],
  works_poorly_with: ["bollinger-bands", "stochastic"],

  example_strategies: [
    "SAR Trailing Stop with EMA-50 Trend Filter (daily F&O)",
    "SAR + ADX Trend Catcher (1h NIFTY)",
  ],

  indian_context:
    "Indian retail F&O scalpers occasionally combine Supertrend AND Parabolic SAR for double-confirmation of intraday trend regime on BANKNIFTY. The combination eliminates many false signals each gives alone. SAR alone is rarely tradeable on Indian indices because they range often; SAR + EMA-50 trend filter on daily NIFTY-500 stocks is a mainstream positional trailing-stop setup. On expiry days, SAR flips in the first hour are often wrong — wait for second-hour confirmation.",
};
