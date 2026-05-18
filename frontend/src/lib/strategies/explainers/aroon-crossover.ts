import type { StrategyExplainer } from "./_types";

export const AROON_CROSSOVER: StrategyExplainer = {
  slug: "aroon-crossover",

  what_it_does:
    "Aroon Up tracks how long ago the highest high occurred in the last N bars; Aroon Down tracks how long ago the lowest low occurred. When Aroon Up crosses ABOVE Aroon Down, a new uptrend is starting (recent highs are fresher than recent lows). When Aroon Down crosses above Aroon Up, a new downtrend.\n\nThis is a trend-INITIATION indicator: it fires at the start of trends, not the middle. Compared to EMA crossovers, Aroon catches trends earlier but produces more false signals in chop.",
  what_it_does_hi:
    "Aroon Up track karta last N bars mein highest high kitne time pehle hua; Aroon Down lowest low kitne time pehle hua. Aroon Up Aroon Down ke UPAR cross kare to new uptrend start ho raha (recent highs fresher hain recent lows se). Aroon Down upar cross kare to new downtrend.\n\nTrend-INITIATION indicator hai: trends ke start pe fires karta, beech mein nahi. EMA crossovers se trends earlier catch karta but chop mein more false signals.",

  best_market_conditions:
    "Markets coming out of consolidation. Stocks breaking out of multi-week ranges. Sector rotation environments where new leadership emerges.",
  worst_market_conditions:
    "Trending markets that are mid-flight (Aroon will already be saturated). Choppy markets where Aroon crossovers fire every 3-5 bars.",

  common_mistakes: [
    "Taking entries during the early-trend signal without checking ADX — Aroon fires before ADX confirms.",
    "Using default period 25 everywhere — for intraday/short-term, period 14 reads new trends faster.",
    "Ignoring the saturation state — if Aroon Up has been at 100 for 10 bars, the 'crossover' already happened.",
  ],

  realistic_returns:
    "Aroon(14) crossover on daily F&O stocks with ADX > 20 filter: 50-57% win rate, R:R 1:2 (catches early). Monthly paper at 1% risk: 3-5%. Without ADX filter, win rate drops to ~42% (too many false starts). Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "INFY",
    entry: "Aroon Up crosses above Aroon Down (Up=86, Down=14) at ₹1,440 — long",
    exit: "Aroon Down crosses above Aroon Up 11 sessions later at ₹1,535",
    pnl: "+6.6% per share (₹95). Position-sized for ₹2,500 risk = ~26 shares = ₹2,470 profit",
  },

  follow_up_strategies: ["adx-strong-trend-filter", "ema-crossover-9-21", "macd-trend-signal"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
