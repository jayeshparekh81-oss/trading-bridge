import type { StrategyExplainer } from "./_types";

export const FIBONACCI_RETRACEMENT_ENTRY: StrategyExplainer = {
  slug: "fibonacci-retracement-entry",

  what_it_does:
    "After a strong directional move (swing low to swing high), price often pulls back to a 'Fibonacci retracement' level (38.2%, 50%, 61.8% of the prior move) before resuming the trend. We mark the most recent swing leg, then enter long on a bullish reversal candle at the 50% or 61.8% pullback level.\n\nFib levels are self-fulfilling to a degree — enough traders watch them that they generate real support/resistance. The edge is modest but real if the prior swing was clear and high-volume.",
  what_it_does_hi:
    "Ek strong directional move (swing low se swing high) ke baad, price often 'Fibonacci retracement' level (38.2%, 50%, 61.8% of prior move) tak pullback hota trend resume hone se pehle. Hum most recent swing leg mark karte, phir 50% ya 61.8% pullback level pe bullish reversal candle pe long enter karte.\n\nFib levels ek degree tak self-fulfilling — enough traders watch them ki real support/resistance generate hota. Edge modest but real hai agar prior swing clear aur high-volume tha.",

  best_market_conditions:
    "Clean directional swings on daily F&O stocks. Trending sectors where pullbacks are buying opportunities.",
  worst_market_conditions:
    "Choppy markets with no clear swing structure. Fib levels in chop are arbitrary points.",

  common_mistakes: [
    "Fitting fib levels to noisy ranges instead of clear swings — if you can't draw the swing in 5 seconds, don't trade the fib.",
    "Entering at the fib level WITHOUT a reversal candle — the level alone is not a signal; the rejection IS.",
    "Stop too far below the 61.8% level — if 61.8% fails, the entire prior swing is invalidated; tight stop is fine.",
  ],

  realistic_returns:
    "Fib retracement (50%/61.8%) entries with reversal candle confirmation on daily F&O stocks: 52-58% win rate, R:R 1:2 (good targets — the prior swing high). Monthly paper at 1% risk: 3-5%. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "BAJFINANCE",
    entry: "Swing from ₹6,800 to ₹7,200 (₹400 move). 61.8% retracement = ₹6,953. Hammer at ₹6,955 — long",
    exit: "Profit target at prior swing high ₹7,200 nine sessions later",
    pnl: "+3.5% per share (₹245). Position-sized for ₹3,000 risk = ~12 shares = ₹2,940 profit",
  },

  follow_up_strategies: ["pivot-point-bounce", "hammer-hanging-man-pattern", "engulfing-candle-reversal"],
  difficulty_score: 3,
  capital_efficiency_score: 4,
};
