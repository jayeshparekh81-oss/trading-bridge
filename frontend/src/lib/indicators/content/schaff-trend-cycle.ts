import type { IndicatorContent } from "./_types";

export const SCHAFF_TREND_CYCLE: IndicatorContent = {
  slug: "schaff-trend-cycle",
  name: "Schaff Trend Cycle (STC)",
  category: "momentum",
  complexity: "advanced",

  one_liner_en:
    "Doug Schaff's enhanced MACD that combines cycle and trend reads — faster and more responsive than vanilla MACD in cyclic markets.",
  one_liner_hi:
    "Doug Schaff ka enhanced MACD jo cycle aur trend reads combine karta — cyclic markets mein vanilla MACD se faster aur more responsive.",

  description_en:
    "Doug Schaff developed STC to address two complaints about classical MACD: it's slow to signal trend changes, and it doesn't work well in cyclic markets. STC combines MACD's trend-detection approach with a stochastic-like cycle smoothing, then double-smooths to remove noise.\n\nThe construction layers three concepts: (1) MACD line (12/26 EMAs), (2) stochastic-style normalization of MACD over a 10-period range, (3) double-smoothing of that stochastic via additional smoothing. The result oscillates 0-100 like a stochastic but reads trend-driven cycles.\n\nReading STC: values above 75 = strong bullish momentum (buy/hold); values below 25 = strong bearish momentum (sell/short). Crosses through 25 (rising) and 75 (falling) are the entry/exit triggers. Schaff's signals are typically 2-5 bars earlier than MACD's, which is a meaningful improvement on daily F&O.\n\nFor Indian retail, STC is most useful in genuinely cycling markets — NIFTY range periods, BANKNIFTY between events. In strong trending periods, STC pins at extremes like other oscillators but its cycle-aware design makes the pinning more obviously diagnostic of 'trend regime'.",
  description_hi:
    "Doug Schaff ne STC develop kiya classical MACD ki do complaints address karne ke liye: trend changes signal karne mein slow, aur cyclic markets mein achha kaam nahi karta. STC MACD ka trend-detection approach aur stochastic-like cycle smoothing combine karta, phir double-smooth karta noise hatane ke liye.\n\nConstruction teen concepts layer karta: (1) MACD line (12/26 EMAs), (2) MACD ka stochastic-style normalization 10-period range pe, (3) us stochastic ka double-smoothing additional smoothing se. Result stochastic ki tarah 0-100 oscillate karta but trend-driven cycles read karta.\n\nSTC reading: 75 ke upar values = strong bullish momentum (buy/hold); 25 ke neeche = strong bearish momentum (sell/short). 25 (rising) aur 75 (falling) ke crosses entry/exit triggers hain. Schaff ke signals typically MACD se 2-5 bars earlier hote, jo daily F&O pe meaningful improvement hai.\n\nIndian retail ke liye STC genuinely cycling markets mein sabse useful — NIFTY range periods, events ke beech BANKNIFTY. Strong trending periods mein STC dusre oscillators ki tarah extremes pe pin hota but iska cycle-aware design pinning ko 'trend regime' ka clearly diagnostic banata.",

  formula_explanation:
    "Step 1: MACD = 12-EMA - 26-EMA. Step 2: Apply stochastic normalization of MACD over 10 bars: STC_K = ((MACD - lowest_MACD[10]) / (highest_MACD[10] - lowest_MACD[10])) × 100. Step 3: Apply EMA smoothing to STC_K (typically 0.5 smoothing factor). Step 4: Apply another stochastic + EMA smoothing on the result. Output: oscillator bounded 0-100. Schaff's recommended cycle length is 10; some implementations use 20.",

  default_period: 10,
  period_range: [10, 23],
  common_periods: [10, 20],

  use_cases: [
    {
      scenario: "Early entry signals in genuinely cycling markets",
      what_to_do: "Long on STC cross above 25; short on STC cross below 75",
      why: "STC fires 2-5 bars earlier than MACD in cycling markets; that earliness compounds over many trades.",
    },
    {
      scenario: "Confirming MACD signals to filter false positives",
      what_to_do: "Take MACD signals only when STC is in agreement (cycle phase aligns)",
      why: "MACD + STC confluence has ~10-15 pp higher win rate than vanilla MACD in cycling Indian markets.",
    },
    {
      scenario: "Avoiding cyclic mean-reversion entries during strong trends",
      what_to_do: "If STC stays > 75 (or < 25) for 5+ bars, the market is trending — don't fade extremes",
      why: "Sustained pin in extreme zone is STC's most reliable 'trend regime' signal; respect it.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish entry",
      condition: "STC crosses above 25 from below",
      action: "Long entry candidate with cycle bottom confirmation.",
    },
    {
      signal: "Bearish entry",
      condition: "STC crosses below 75 from above",
      action: "Long exit / short entry candidate.",
    },
    {
      signal: "Bullish divergence",
      condition: "Price lower low, STC higher low",
      action: "Strong bullish reversal candidate; pair with support test.",
    },
    {
      signal: "Trend regime pinning",
      condition: "STC remains in extreme zone (>75 or <25) for 5+ bars",
      action: "Trend is dominating; do not trade STC extremes against the trend.",
    },
  ],

  pitfalls: [
    "Earlier signals = more false positives in choppy markets; pair with ADX > 20 filter.",
    "Complex calculation makes STC hard to verify manually — sanity-check against MACD direction.",
    "Default 10-period cycle assumption may not fit all instruments — check the actual cycle length first.",
    "On strong trends, STC pins at 100 or 0 for many bars; cycle interpretation breaks down.",
    "Confusion with raw stochastic — STC has trend-aware construction but visually resembles stochastic.",
  ],

  works_well_with: ["adx", "ema", "bollinger-bands", "supports-resistances"],
  works_poorly_with: ["macd", "stochastic"],

  example_strategies: [
    "Schaff cyclic mean-reversion on NIFTY daily (low-VIX regimes)",
    "STC + MACD confluence on F&O cash equity",
    "STC divergence at support levels for swing reversals",
  ],

  indian_context:
    "STC on NIFTY daily works particularly well during pre-event consolidation periods (pre-budget, pre-Fed meeting) where cycles dominate. During trending months, STC pinning identifies the 'don't fight the trend' regime more cleanly than MACD does. BANKNIFTY's higher beta means STC cycles are sharper and signals more frequent — useful for tactical trading but requires stricter risk management. For F&O equity, STC works well on mid-cap names (Power Grid, NTPC) where cyclical patterns are visible; less so on persistent-trend large-caps. Avoid STC on small-caps due to noisy stochastic normalization.",
};
