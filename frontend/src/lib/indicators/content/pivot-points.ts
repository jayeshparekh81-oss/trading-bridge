import type { IndicatorContent } from "./_types";

export const PIVOT_POINTS: IndicatorContent = {
  slug: "pivot-points",
  name: "Pivot Points (Standard + CPR)",
  category: "pattern",
  complexity: "intermediate",

  one_liner_en:
    "Floor-trader levels computed from yesterday's high/low/close. CPR (Central Pivot Range) is the Indian retail favourite variant.",
  one_liner_hi:
    "Floor-trader levels jo kal ke high/low/close se compute hote. CPR (Central Pivot Range) Indian retail favourite variant hai.",

  description_en:
    "Pivot Points were used by floor traders before electronic charting — a few simple arithmetic formulas turn yesterday's OHLC into today's reference support/resistance levels. The standard set is the pivot (PP), three resistances (R1, R2, R3), and three supports (S1, S2, S3). All seven levels are plotted as horizontal lines that don't move during the day.\n\nThe Indian retail favourite variant is **CPR (Central Pivot Range)**: instead of one pivot line, CPR plots three closely-spaced lines — Top Central (TC), Pivot (PP), Bottom Central (BC). When TC-BC is wide, the day is likely to be range-bound; when TC-BC is narrow, the day is likely to trend. The 'narrow CPR' setup is one of the most-discussed Indian intraday patterns.\n\nUse cases:\n• **Intraday support/resistance**: Treat S1-R1 as today's likely range. A break of R1 with volume often runs to R2.\n• **CPR-based bias**: Price opening above CPR = bullish bias; below = bearish; inside = neutral / range-bound.\n• **Multi-day setups**: Weekly and monthly pivots (computed from prior week/month OHLC) are positional reference levels.\n\nPivots don't move during the day — that's their strength (objective, predetermined levels) and their weakness (don't adapt to intraday news).",
  description_hi:
    "Pivot Points electronic charting se pehle floor traders use karte the — kuch simple arithmetic formulas kal ke OHLC ko aaj ke reference support/resistance levels mein convert karte hain. Standard set mein pivot (PP), teen resistances (R1, R2, R3), teen supports (S1, S2, S3) hain. Saare saat levels horizontal lines hain jo din mein move nahi karte.\n\nIndian retail favourite variant **CPR (Central Pivot Range)** hai: ek pivot line ke bajaye, CPR teen closely-spaced lines plot karta — Top Central (TC), Pivot (PP), Bottom Central (BC). TC-BC chodi hai to day likely range-bound; narrow hai to day likely trend. 'Narrow CPR' setup most-discussed Indian intraday patterns mein se ek hai.\n\nUse cases:\n• **Intraday support/resistance**: S1-R1 ko aaj ki likely range maano. R1 break with volume often R2 tak run karta.\n• **CPR-based bias**: Price CPR ke upar open ho = bullish bias; neeche = bearish; andar = neutral / range-bound.\n• **Multi-day setups**: Weekly aur monthly pivots (prior week/month OHLC se computed) positional reference levels hain.\n\nPivots din mein move nahi karte — yeh strength hai (objective, predetermined levels) aur weakness (intraday news pe adapt nahi karte).",

  formula_explanation:
    "Standard: PP = (high + low + close) / 3. R1 = 2×PP - low. S1 = 2×PP - high. R2 = PP + (high - low). S2 = PP - (high - low). R3 = high + 2×(PP - low). S3 = low - 2×(high - PP).\n\nCPR additions: BC = (high + low) / 2. TC = 2×PP - BC. The three CPR lines (TC, PP, BC) are computed from yesterday's OHLC.\n\nAll levels are computed at market open and stay fixed all day.",

  default_period: null,
  period_range: null,
  common_periods: [],

  use_cases: [
    {
      scenario: "Intraday range play with CPR width",
      what_to_do: "Measure TC-BC. If today's TC-BC is narrower than yesterday's, expect a trending day. Trade breakouts. Wide CPR = range day, fade extremes",
      why: "Empirically, narrow-CPR days have higher trend persistence — the most-replicated intraday setup in Indian retail.",
    },
    {
      scenario: "Opening-gap interpretation",
      what_to_do: "If price opens far above R1, treat it as gap-up trend day; if it opens far below S1, gap-down trend day",
      why: "Pre-market gaps that clear nearest pivot levels usually have follow-through, not fade — pivots make the magnitude objective.",
    },
    {
      scenario: "Multi-timeframe pivot confluence",
      what_to_do: "Mark daily, weekly, and monthly pivots. Levels where multiple timeframes overlap are exceptional support/resistance",
      why: "Confluence levels concentrate participant attention — high-conviction reversal / breakout zones.",
    },
  ],

  common_signals: [
    {
      signal: "Narrow CPR day",
      condition: "Today's TC-BC is in the lowest 25% of recent values",
      action: "Trending-day setup — trade pivot-level breakouts.",
    },
    {
      signal: "Wide CPR day",
      condition: "Today's TC-BC is in the highest 25% of recent values",
      action: "Range-day setup — fade R1 / S1 touches.",
    },
    {
      signal: "PP reclaim",
      condition: "Price recovers above PP after spending time below",
      action: "Intraday bias shift — long candidate.",
    },
    {
      signal: "R1 break with volume",
      condition: "Price closes above R1 with volume > 1.5× average",
      action: "Continuation long — target R2.",
    },
  ],

  pitfalls: [
    "Pivot levels are predetermined and don't adapt to news. A major event mid-session can blow through all 7 levels and the indicator goes silent.",
    "Multiple pivot 'systems' exist (Standard, Fibonacci, Camarilla, Woodie's). Each gives different levels. Be consistent.",
    "CPR's 'narrow vs wide' is relative — what's narrow on NIFTY is normal on BANKNIFTY. Compare against the symbol's own recent history.",
    "Levels are based on PREVIOUS day's OHLC. On Monday, the 'previous day' is Friday — be aware your charting tool may include or exclude weekends differently.",
    "Pivot break + immediate reverse (fakeout) is common in Indian markets, especially first 15 min. Wait for confirmation.",
  ],

  works_well_with: ["vwap", "volume-profile", "supertrend", "atr"],
  works_poorly_with: ["bollinger-bands", "donchian-channel"],

  example_strategies: [
    "CPR Narrow Range Breakout (intraday NIFTY / BANKNIFTY)",
    "Pivot Level Reversal (1h F&O stocks)",
    "Multi-Timeframe Pivot Confluence (positional)",
  ],

  indian_context:
    "CPR is arguably the single most-discussed indicator in Indian intraday F&O after Supertrend. The narrow-CPR / wide-CPR distinction is foundational in Indian retail intraday strategy — countless Telegram channels, YouTube videos, and trading-academy courses are built around it. Floor-pivot levels on daily NIFTY align reasonably with intraday institutional reference points; on BANKNIFTY, pivots are wider due to higher beta. Weekly pivots are useful for swing trades on F&O stocks. The Standard pivot formula is the most common Indian setting; some traders prefer Camarilla for tighter day-trade ranges.",
};
