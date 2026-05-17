import type { StrategyExplainer } from "./_types";

export const MACD_HISTOGRAM_MOMENTUM: StrategyExplainer = {
  slug: "macd-histogram-momentum",

  what_it_does:
    "The MACD histogram is the gap between the MACD line and its signal line — visualised as bars above/below zero. A growing positive histogram means bullish momentum is accelerating; a shrinking histogram means momentum is fading. We enter long when the histogram first prints a green bar after being red, and exit when it prints its first red bar after being green.\n\nThis is a faster, more sensitive read than waiting for the MACD signal-line cross itself. The trade-off: more signals, more noise, more whipsaws in chop.",
  what_it_does_hi:
    "MACD histogram MACD line aur signal line ka gap hai — bars ki tarah zero ke upar/neeche visualised. Growing positive histogram = bullish momentum accelerating; shrinking = momentum fading. Histogram red ke baad pehla green bar print kare to long enter; green ke baad pehla red bar print kare to exit.\n\nMACD signal-line cross ka wait karne se faster, more sensitive read. Trade-off: more signals, more noise, more whipsaws in chop.",

  best_market_conditions:
    "Trending markets with rising ADX. Daily charts of NSE F&O stocks during sector rotation.",
  worst_market_conditions:
    "Chop where histogram flips colour every 2-3 bars. Expiry-week intraday on indices.",

  common_mistakes: [
    "Trading every colour flip without a trend filter — chop produces 10+ false flips per week.",
    "Ignoring histogram height — a tiny green bar after red means weak momentum; wait for sustained colour.",
    "Holding through 2-3 contrary bars 'in case momentum returns' — the colour change IS the signal; respect it.",
  ],

  realistic_returns:
    "MACD histogram on daily F&O with ADX > 20 filter: 50-58% win rate, R:R 1:1.6. Monthly paper at 1% risk: 2-5%. Without ADX filter, returns turn negative in choppy months.",

  example_trade: {
    symbol: "HDFCBANK",
    entry: "MACD histogram prints first green bar after 4 red bars, ADX = 24 — long at ₹1,590",
    exit: "Histogram prints first red bar 7 sessions later at ₹1,648",
    pnl: "+3.6% per share (₹58). Position-sized for ₹2,000 risk = ~30 shares = ₹1,740 profit",
  },

  follow_up_strategies: ["macd-trend-signal", "macd-divergence", "rsi-macd-confluence"],
  difficulty_score: 2,
  capital_efficiency_score: 3,
};
