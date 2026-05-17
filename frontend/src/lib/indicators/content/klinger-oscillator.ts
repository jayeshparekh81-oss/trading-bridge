import type { IndicatorContent } from "./_types";

export const KLINGER_OSCILLATOR: IndicatorContent = {
  slug: "klinger-oscillator",
  name: "Klinger Volume Oscillator (KVO)",
  category: "volume",
  complexity: "advanced",

  one_liner_en:
    "Tracks long-term money flow vs short-term — signals reversals when KVO crosses its signal line at extremes.",
  one_liner_hi:
    "Long-term vs short-term money flow track karta — KVO signal line cross kare extremes pe to reversal signal.",

  description_en:
    "Stephen Klinger developed the Klinger Volume Oscillator to compare long-term volume flow against short-term volume flow. The construction is more complex than typical oscillators: it uses the daily 'trend' (whether today's H+L+C is above or below yesterday's) and applies that direction as a sign to that day's volume contribution. Cumulative signed volumes are then summed and differenced via long/short EMAs.\n\nThe output oscillates around zero and is read with a signal line (typically 13-period EMA of KVO). Standard crosses give entry/exit signals; divergence at extremes gives the strongest reversal setups.\n\nKlinger argued that volume LEADS price — peaks in money flow occur slightly before peaks in price. KVO's design tries to surface this leading edge. In practice on Indian F&O, the leading effect is often 1-3 bars at the daily timeframe, which is enough to make a difference on tight risk-reward setups.\n\nKVO is more advanced and harder to read than OBV or PVT. The trade-off is signal quality — when KVO signals fire (especially with divergence at extremes), the hit-rate on daily F&O is meaningfully higher than simpler volume indicators.",
  description_hi:
    "Stephen Klinger ne Klinger Volume Oscillator develop kiya long-term volume flow ko short-term volume flow ke against compare karne ke liye. Construction typical oscillators se complex hai: ye daily 'trend' use karta (kya aaj ka H+L+C kal se upar ya neeche) aur us direction ko us din ke volume contribution pe sign ki tarah apply karta. Cumulative signed volumes phir sum hote aur long/short EMAs ke through differenced.\n\nOutput zero ke around oscillate karta aur signal line (typically KVO ka 13-period EMA) ke saath read hota. Standard crosses entry/exit signals dete; extremes pe divergence strongest reversal setups deta.\n\nKlinger ne argue kiya volume price LEADS karta — money flow ke peaks price ke peaks se slightly pehle hote. KVO ka design is leading edge ko surface karne ki koshish karta. Indian F&O pe practice mein leading effect daily timeframe pe often 1-3 bars hota, jo tight risk-reward setups pe difference banata.\n\nKVO OBV ya PVT se more advanced aur harder to read hai. Trade-off signal quality hai — KVO signals fire kare (especially extremes pe divergence ke saath), daily F&O pe hit-rate simpler volume indicators se meaningfully higher hota.",

  formula_explanation:
    "Step 1: Daily Trend = +1 if (High+Low+Close)[today] > (High+Low+Close)[yesterday], else -1. Step 2: Daily Measurement = abs(2 × ((dm/cm) - 1)) × Trend × Volume × 100, where dm = High-Low and cm is cumulative dm. Step 3: KVO = 34-period EMA of Daily Measurement - 55-period EMA of Daily Measurement. Step 4: Signal Line = 13-period EMA of KVO. The EMAs at 34, 55, 13 are Klinger's original parameters.",

  default_period: 34,
  period_range: [13, 55],
  common_periods: [13, 34, 55],

  use_cases: [
    {
      scenario: "Trend confirmation on multi-day positional trades",
      what_to_do: "Use KVO direction (positive/negative) as a bias filter for swing entries",
      why: "KVO's long-term/short-term EMA structure filters out short-term noise, giving a cleaner bias read than raw volume.",
    },
    {
      scenario: "Divergence-based reversal trades",
      what_to_do: "Price higher high, KVO lower high at known resistance = high-conviction bearish reversal setup",
      why: "KVO divergence at structural levels is one of the higher-quality reversal signals among volume indicators.",
    },
    {
      scenario: "Avoiding fake breakouts",
      what_to_do: "If price breaks resistance but KVO is below zero or falling, treat the breakout as suspicious",
      why: "Breakouts without volume conviction (as measured by KVO) tend to reverse within 3-5 sessions.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish signal cross",
      condition: "KVO crosses above its 13-period signal line, ideally below zero",
      action: "Long entry candidate with volume confirmation.",
    },
    {
      signal: "Bearish signal cross",
      condition: "KVO crosses below signal line, ideally above zero",
      action: "Long exit / short entry candidate.",
    },
    {
      signal: "Bullish divergence",
      condition: "Price lower low, KVO higher low",
      action: "Strong bullish reversal candidate at established support.",
    },
    {
      signal: "Centerline cross",
      condition: "KVO crosses zero line",
      action: "Major trend bias shift — adjust positional outlook.",
    },
  ],

  pitfalls: [
    "Complex calculation makes KVO hard to verify manually — pair with simpler indicators (OBV, MFI) for sanity check.",
    "Sensitive to gap moves; gap-heavy stocks produce noisy KVO readings.",
    "Default periods (34, 55, 13) are calibrated for daily charts; recalibrate for intraday use.",
    "False signals frequent in low-volatility consolidation; pair with ADX > 20 filter.",
    "On index futures, KVO suffers from hedging-volume distortion like all volume indicators.",
  ],

  works_well_with: ["obv", "supports-resistances", "ema", "adx"],
  works_poorly_with: ["price-volume-trend", "mfi"],

  example_strategies: [
    "Klinger divergence trader on F&O cash equity daily",
    "KVO + EMA trend filter on positional swing trades",
    "KVO breakout confirmation overlay on price-action breakouts",
  ],

  indian_context:
    "KVO on NIFTY F&O cash equity (especially RIL, HDFC Bank, ICICI Bank) provides leading signals 1-3 days ahead of price moves during institutional accumulation phases. FII activity often shows up in KVO before it shows in NIFTY price. BANKNIFTY constituents during sector rotation (e.g., 2023 PSU bank rally) showed clean KVO accumulation patterns 1-2 weeks before price broke out. Avoid using KVO on NIFTY/BANKNIFTY futures (hedging distortion). For F&O cash equity mid-caps like Tata Power and Adani Ports, KVO divergence at all-time-highs has historically caught major reversals.",
};
