import type { IndicatorContent } from "./_types";

export const DETRENDED_PRICE_OSCILLATOR: IndicatorContent = {
  slug: "detrended-price-oscillator",
  name: "Detrended Price Oscillator (DPO)",
  category: "momentum",
  complexity: "intermediate",

  one_liner_en:
    "Removes the trend from price to expose underlying cycles — best for identifying cycle peaks and troughs.",
  one_liner_hi:
    "Price se trend hata ke underlying cycles dikhata — cycle peaks aur troughs identify karne ke liye best.",

  description_en:
    "The Detrended Price Oscillator (DPO) is built for a specific purpose: take price, REMOVE the trend, and what's left is the cycle. Most indicators include trend in their reading. DPO actively strips trend out so the trader can see cycle structure cleanly.\n\nMechanically, DPO subtracts a SHIFTED simple moving average from the price. The shift is `(period/2) + 1` bars backwards, which centres the MA on the price being subtracted from. This shifting is crucial — without it, you'd just have a price-minus-MA which still encodes recent trend. The shift makes DPO history-only (the last few bars are blank by design).\n\nWhat does DPO tell you? Cycles. If price oscillates up and down around the trend, DPO traces those swings as positive and negative deviations from zero. Peaks in DPO mark cycle tops; troughs mark cycle bottoms. The depth and frequency of these cycles is much clearer in DPO than in raw price.\n\nDPO doesn't predict future prices — the recent bars are unfilled. It's a backward-looking analytical tool. Use it to STUDY market cycles for a specific instrument (does it cycle every 20 bars? every 35?), then use that knowledge to time other entries.",
  description_hi:
    "Detrended Price Oscillator (DPO) specific purpose ke liye banaya: price lo, trend HATAO, jo bachta wo cycle hai. Zyadatar indicators reading mein trend include karte. DPO actively trend strip out karta taaki trader cycle structure cleanly dekh sake.\n\nMechanically, DPO price se ek SHIFTED simple moving average subtract karta. Shift `(period/2) + 1` bars backwards hota, jo MA ko subtract-from-price pe centre karta. Ye shifting crucial hai — bina iske, sirf price-minus-MA hota jo abhi bhi recent trend encode karta. Shift DPO ko history-only banata (last few bars by design blank).\n\nDPO kya batata? Cycles. Agar price trend ke around up-down oscillate kare, DPO un swings ko zero se positive aur negative deviations ke roop mein trace karta. DPO mein peaks cycle tops mark karte; troughs cycle bottoms mark karte. In cycles ki depth aur frequency raw price se DPO mein bahut zyada clear hoti.\n\nDPO future prices predict nahi karta — recent bars unfilled hote. Backward-looking analytical tool hai. Specific instrument ke market cycles STUDY karne ke liye use karo (kya 20 bars mein cycle hota? 35 mein?), phir wo knowledge dusre entries time karne mein use karo.",

  formula_explanation:
    "DPO = Close[today] - SMA[period][today shifted back (period/2 + 1) bars]. With period 20, you'd subtract the 20-period SMA centered 11 bars in the past from today's close. The shift means the indicator doesn't give a reading for the most recent (period/2 + 1) bars — that's intentional and what makes it 'detrended' rather than 'trend-following'.",

  default_period: 20,
  period_range: [10, 50],
  common_periods: [14, 20, 30],

  use_cases: [
    {
      scenario: "Studying cycle length of a specific instrument",
      what_to_do: "Plot DPO with different periods (14, 20, 30) and visually count peak-to-peak distance",
      why: "Each instrument has its own dominant cycle length — knowing it (say NIFTY's ~22-bar daily cycle) sharpens timing on cycle-aware strategies.",
    },
    {
      scenario: "Confirming that a cycle is dominating, not a trend",
      what_to_do: "If DPO oscillates cleanly between +X and -X, the market is cycling; if DPO drifts persistently, a trend is overwhelming the cycle",
      why: "Cycle-based entry rules only work when cycles dominate; this is the diagnostic test.",
    },
    {
      scenario: "Calibrating cycle-aware strategies (e.g. Hilbert transform, Schaff)",
      what_to_do: "Use DPO peak counts to inform period parameters in more complex cycle indicators",
      why: "Many advanced indicators have a 'cycle period' parameter; DPO is the simplest way to measure what value to plug in.",
    },
  ],

  common_signals: [
    {
      signal: "Cycle peak",
      condition: "DPO crosses below a local maximum (e.g., previous peak)",
      action: "Cycle top reached — consider profit-taking on cycle-aligned longs.",
    },
    {
      signal: "Cycle trough",
      condition: "DPO crosses above a local minimum (e.g., previous trough)",
      action: "Cycle bottom reached — cycle-aware long entry.",
    },
    {
      signal: "Cycle dominance",
      condition: "DPO oscillates symmetrically between roughly equal positive and negative extremes",
      action: "Market is in cycling regime — cycle-based strategies are viable.",
    },
  ],

  pitfalls: [
    "DPO doesn't give a reading for the most recent (period/2 + 1) bars — that's by design, not a bug.",
    "Not a leading indicator — never use DPO as an entry trigger by itself.",
    "Cycles vary over time — a cycle length measured in one regime may not hold a year or two later. Re-measure periodically.",
    "On strongly trending markets, DPO has no information — its zero readings just mean 'trend dominates'.",
    "Common mistake: comparing DPO across instruments. Magnitudes are price-scaled and not directly comparable.",
  ],

  works_well_with: ["macd", "rsi", "stochastic"],
  works_poorly_with: ["ema", "sma", "supertrend"],

  example_strategies: [
    "Cycle length discovery for NIFTY daily",
    "DPO + RSI cycle bottom entry",
    "Cycle confirmation overlay on trend-following strategies",
  ],

  indian_context:
    "NIFTY daily chart has historically shown roughly cyclical structure in DPO that can be useful for swing traders timing entries around index expiry weeks — measure the current cycle length on your own data rather than assuming a fixed number. BANKNIFTY tends to have shorter cycles due to higher beta. Avoid using DPO during budget/election event weeks where cycles get disrupted by news flow. For F&O stocks, large caps (RIL, HDFC Bank) tend to show cleaner DPO cycles; mid-caps are more erratic and DPO loses utility.",
};
