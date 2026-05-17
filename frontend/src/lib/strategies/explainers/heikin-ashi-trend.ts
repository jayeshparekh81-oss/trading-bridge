import type { StrategyExplainer } from "./_types";

export const HEIKIN_ASHI_TREND: StrategyExplainer = {
  slug: "heikin-ashi-trend",

  what_it_does:
    "Heikin Ashi (HA) candles are SMOOTHED candles — each HA candle uses an average of the prior HA candle's open/close instead of raw OHLC. The result: consecutive HA candles in the same direction (without shadow on the opposite side) signal a clean trend. We enter long when HA prints 2 consecutive green candles with no upper shadow; exit on the first HA candle with a lower shadow (sign of selling pressure entering).\n\nThe trade-off: HA candles LAG real price; entries are a bar or two late, but you stay in trends much longer than with raw candle reads.",
  what_it_does_hi:
    "Heikin Ashi (HA) candles SMOOTHED candles hain — har HA candle prior HA candle ke open/close ka average use karta raw OHLC ki jagah. Result: same direction mein consecutive HA candles (opposite side pe shadow ke bina) clean trend signal karta. Long enter karte jab HA 2 consecutive green candles bina upper shadow ke print kare; exit jab first HA candle lower shadow ke saath aaye (selling pressure entering).\n\nTrade-off: HA candles real price se LAG karte; entries bar do bar late hote, but trends mein much longer stay karte raw candles se.",

  best_market_conditions:
    "Strong sustained trends on daily charts. Sector breakouts that run 10+ sessions.",
  worst_market_conditions:
    "Choppy markets where HA candles alternate colour every bar. Pre-event consolidations.",

  common_mistakes: [
    "Reading HA as real price levels — HA open/close are calculated, not actual prices; use real candles for stops.",
    "Exiting on the FIRST counter-candle without a shadow — the rule requires a SHADOW (selling pressure visible).",
    "Using HA on 5-min intraday — too smoothed for that timeframe; HA's edge is on daily/weekly.",
  ],

  realistic_returns:
    "Heikin Ashi 2-consecutive-no-shadow trend follow on daily F&O stocks with ADX > 20: 50-58% win rate, R:R 1:2.2 (rides trends well). Monthly paper at 1% risk: 3-5%. Lag means worst-case losers are bigger than entry-perfect setups.",

  example_trade: {
    symbol: "LT",
    entry: "HA prints 2 consecutive green candles, no upper shadow. Real price = ₹3,560 — long",
    exit: "HA prints green candle with lower shadow at real price ₹3,820, 16 sessions later",
    pnl: "+7.3% per share (₹260). Position-sized for ₹3,000 risk = ~12 shares = ₹3,120 profit",
  },

  follow_up_strategies: ["adx-strong-trend-filter", "chandelier-exit-trail", "supertrend-rider"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
