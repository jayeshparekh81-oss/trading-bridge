import type { StrategyExplainer } from "./_types";

export const TRIPLE_EMA_CROSSOVER: StrategyExplainer = {
  slug: "triple-ema-crossover",

  what_it_does:
    "Three EMAs (typically 9, 21, 50) layered together. Long entry requires alignment: EMA9 > EMA21 > EMA50 AND price > EMA9. The three-tier alignment confirms momentum on multiple timeframes simultaneously — short-term (9 vs 21), medium-term (21 vs 50), and price-relative (price vs 9).\n\nThis is a higher-conviction version of the basic EMA crossover. Fewer entries fire (the alignment requirement is strict) but win rate is meaningfully higher than 2-EMA crossover.",
  what_it_does_hi:
    "Teen EMAs (typically 9, 21, 50) layered. Long entry chahiye alignment: EMA9 > EMA21 > EMA50 AND price > EMA9. Three-tier alignment momentum confirm karta multiple timeframes pe simultaneously — short-term (9 vs 21), medium-term (21 vs 50), aur price-relative (price vs 9).\n\nBasic EMA crossover ka higher-conviction version. Fewer entries fire (alignment requirement strict hai) but win rate 2-EMA crossover se meaningfully higher.",

  best_market_conditions:
    "Sustained trending markets where the alignment can hold for weeks. Sector breakouts.",
  worst_market_conditions:
    "Choppy markets — alignment makes and unmakes every 4-5 bars; you sit out most of the year.",

  common_mistakes: [
    "Entering on partial alignment — if EMA9 < EMA50 (out of order), the trend isn't confirmed across timeframes.",
    "Using too-short periods (5/13/34) — that defeats the multi-timeframe purpose.",
    "Exiting on a single EMA flip — exit when alignment FULLY breaks (EMA9 < EMA21), not on a single bar fluctuation.",
  ],

  realistic_returns:
    "Triple-EMA (9/21/50) full alignment on daily F&O stocks: 55-62% win rate, R:R 1:2 (winners run longer than 2-EMA). Monthly paper at 1% risk: 3-5%. Fires 4-8 setups per month per stock. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "ULTRACEMCO",
    entry: "Alignment forms: EMA9 ₹10,520 > EMA21 ₹10,495 > EMA50 ₹10,450. Price ₹10,560 — long",
    exit: "EMA9 crosses below EMA21 at ₹11,020 nineteen sessions later",
    pnl: "+4.4% per share (₹460). Position-sized for ₹3,000 risk = ~7 shares = ₹3,220 profit",
  },

  follow_up_strategies: ["ema-crossover-9-21", "ema-crossover-20-50", "adx-strong-trend-filter"],
  difficulty_score: 1,
  capital_efficiency_score: 4,
};
