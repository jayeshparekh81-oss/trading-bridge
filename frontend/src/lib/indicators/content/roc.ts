import type { IndicatorContent } from "./_types";

export const ROC: IndicatorContent = {
  slug: "roc",
  name: "ROC (Rate of Change)",
  category: "rate",
  complexity: "beginner",

  one_liner_en:
    "Percentage price change over the last N bars. Direct momentum measurement, unbounded.",
  one_liner_hi:
    "Last N bars mein percentage price change. Direct momentum measurement, unbounded.",

  description_en:
    "ROC is one of the simplest momentum indicators — just the percent change between today's close and the close `period` bars ago. Output oscillates around zero: positive means price is higher than `period` bars ago (uptrend over the lookback), negative means lower (downtrend).\n\nUnlike RSI / Stochastic / MFI which are bounded 0-100, ROC has no ceiling or floor. A 5% return over 14 days reads as +5; a 20% return reads as +20. That makes magnitudes directly comparable across stocks and time — unlike RSI where 80 means different things in different volatility regimes.\n\nThree primary uses:\n• **Zero-line cross**: ROC > 0 = bullish bias, < 0 = bearish bias. Simple trend filter.\n• **Extreme readings**: very high (>10% on a 14-period daily) often precedes mean reversion; very low (-10%+) often precedes a bounce. Thresholds are symbol-specific because of volatility.\n• **Divergence**: same logic as RSI / MACD — price new high, ROC lower high = momentum waning.\n\nROC is often the building block for fancier indicators (Momentum, TSI, KST). On its own it's underrated for being so simple — many quant systems use ROC as their core 'momentum' input.",
  description_hi:
    "ROC sabse simple momentum indicators mein se ek — sirf aaj ke close aur `period` bars pehle ke close ka percent change. Output zero ke around oscillate karta: positive matlab price `period` bars pehle se higher (lookback over uptrend), negative matlab lower (downtrend).\n\nRSI / Stochastic / MFI bounded 0-100 hain, ROC ke unlike. ROC ka koi ceiling ya floor nahi. 14 din mein 5% return = +5; 20% return = +20. Magnitudes stocks aur time ke across directly comparable — RSI ke unlike jahan 80 different volatility regimes mein different cheez means karta.\n\nTeen primary uses:\n• **Zero-line cross**: ROC > 0 = bullish bias, < 0 = bearish. Simple trend filter.\n• **Extreme readings**: very high (>10% on 14-period daily) often mean reversion se pehle hota; very low (-10%+) often bounce se pehle. Thresholds symbol-specific hain volatility ki wajah se.\n• **Divergence**: RSI / MACD ki same logic — price new high, ROC lower high = momentum waning.\n\nROC often fancier indicators (Momentum, TSI, KST) ka building block hai. Akela rehte hue underrated hai itne simple hone ke liye — many quant systems ROC ko apna core 'momentum' input use karte hain.",

  formula_explanation:
    "ROC = ((close - close[period bars ago]) / close[period bars ago]) × 100. Output is in percentage points. Default period: 12. No smoothing, no constants — pure percent-change calculation.",

  default_period: 12,
  period_range: [3, 100],
  common_periods: [10, 12, 14, 20, 50],

  use_cases: [
    {
      scenario: "Cross-stock momentum ranking",
      what_to_do: "Compute ROC(20) on every F&O stock. Rank by value. Top decile = momentum leaders for the look-back window.",
      why: "Because ROC is unbounded and directly comparable across symbols, ranking is straightforward — much harder with RSI / Stochastic.",
    },
    {
      scenario: "Trend-bias filter",
      what_to_do: "Only take long signals when ROC > 0 (i.e. price is higher than `period` bars ago)",
      why: "Simplest possible trend filter — removes most counter-trend longs.",
    },
    {
      scenario: "Divergence at key swing levels",
      what_to_do: "At a swing high test, watch for ROC to make a lower high while price prints a new high",
      why: "Divergence signals momentum decay — actionable when paired with a candle reversal pattern.",
    },
  ],

  common_signals: [
    {
      signal: "Zero-line cross up",
      condition: "ROC crosses above 0 from below",
      action: "Bullish bias — enable long-only strategies.",
    },
    {
      signal: "Zero-line cross down",
      condition: "ROC crosses below 0 from above",
      action: "Bearish bias — switch to short or stand aside.",
    },
    {
      signal: "Extreme high reading",
      condition: "ROC pushes far above its own recent range",
      action: "Trend extension — consider tightening stops on existing longs.",
    },
  ],

  pitfalls: [
    "Unbounded. A 'high' ROC for one stock is normal for another. Always evaluate relative to the stock's own historical ROC distribution, not absolute thresholds.",
    "Sensitive to the lookback period. ROC(5) and ROC(50) tell totally different stories about the same chart.",
    "On gap days, ROC jumps unnaturally; the indicator doesn't model the gap as separate from intraday movement.",
    "Divergence signals fire less frequently on ROC than on RSI / MACD (no smoothing dampens noise) — that's a feature for some, a bug for others.",
  ],

  works_well_with: ["macd", "rsi", "ema", "adx"],
  works_poorly_with: ["momentum", "tsi"],

  example_strategies: [
    "ROC Ranked Momentum Portfolio (weekly NSE-500 stocks)",
    "ROC Zero-Cross Trend Filter (daily F&O)",
    "ROC Divergence Hunter (1h NIFTY)",
  ],

  indian_context:
    "ROC(20) on the daily is a common ranking metric in Indian momentum-investing strategies — sector-rotation funds and quant retail use it to score F&O stocks weekly. NIFTY's daily ROC(12) historically averages around +0.5% in bull markets and -0.5% in bears; extremes above +5% or below -5% on the index are once-or-twice-a-year events tied to major macro moves. For F&O stocks with earnings, ROC(5) catches the immediate post-results momentum more cleanly than slower indicators because of its zero smoothing.",
};
