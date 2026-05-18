import type { StrategyExplainer } from "./_types";

export const HULL_MA_TREND: StrategyExplainer = {
  slug: "hull-ma-trend",

  what_it_does:
    "The Hull Moving Average (HMA) is a low-lag moving average that uses weighted MAs and a square-root smoothing trick to dramatically reduce the lag that plagues SMA/EMA. The trade rule: enter long when HMA slopes upward (current HMA > 2 bars ago); exit when it slopes down.\n\nCompared to EMA, HMA catches trend changes 3-6 bars earlier — at the cost of being slightly noisier in chop. It's the favourite MA of many shorter-term trend traders for exactly that lag-vs-noise trade-off.",
  what_it_does_hi:
    "Hull Moving Average (HMA) ek low-lag moving average hai jo weighted MAs aur square-root smoothing trick use karta SMA/EMA ka lag dramatically reduce karne ke liye. Trade rule: HMA upward slope kare (current HMA > 2 bars ago) to long enter; downward slope to exit.\n\nEMA se compare karke, HMA trend changes 3-6 bars earlier catch karta — cost: chop mein slightly noisier. Many shorter-term trend traders ka favourite MA exactly is lag-vs-noise trade-off ke liye.",

  best_market_conditions:
    "Trending markets where catching the turn early matters. Swing trades on F&O stocks.",
  worst_market_conditions:
    "Choppy markets — HMA's reduced lag becomes a liability; you get more whipsaws than EMA.",

  common_mistakes: [
    "Switching to HMA in choppy markets thinking 'lower lag = better' — actually higher whipsaw cost.",
    "Using HMA period too short (< 9) — that magnifies noise; period 14-21 is sweet spot.",
    "Trading HMA cross without any filter — pair with ADX or volume for fewer false signals.",
  ],

  realistic_returns:
    "HMA(14) slope flip with ADX > 20 filter on daily F&O: 52-58% win rate, R:R 1:1.8. Monthly paper at 1% risk: 3-4%. Wins compound faster than EMA because of earlier entry, but loses more in chop. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "MARUTI",
    entry: "HMA(14) slope flips up at ₹11,400, ADX = 24 — long",
    exit: "HMA slope flips down at ₹11,820 thirteen sessions later",
    pnl: "+3.7% per share (₹420). Position-sized for ₹3,000 risk = ~7 shares = ₹2,940 profit",
  },

  follow_up_strategies: ["ema-crossover-9-21", "adx-strong-trend-filter", "supertrend-rider"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
