import type { StrategyExplainer } from "./_types";

export const CHANDELIER_EXIT_TRAIL: StrategyExplainer = {
  slug: "chandelier-exit-trail",

  what_it_does:
    "A volatility-adjusted trailing stop. For a long position, Chandelier Exit = highest high of last 22 bars MINUS 3 × ATR(22). As the underlying makes new highs, the stop ratchets up; when it pulls back more than 3 ATRs from the recent high, the stop hits and the trade exits.\n\nThis is not an ENTRY signal — it's an EXIT/trail management overlay you bolt onto any trend-following entry (EMA cross, MACD, Supertrend). The 3-ATR distance gives trends room to breathe while still bailing on real reversals.",
  what_it_does_hi:
    "Volatility-adjusted trailing stop. Long position ke liye, Chandelier Exit = last 22 bars ka highest high MINUS 3 × ATR(22). Underlying naye highs banata jaaye to stop ratchet up hota; recent high se 3 ATRs se zyada pullback ho to stop hit, trade exit.\n\nYe ENTRY signal nahi — EXIT/trail management overlay hai jo trend-following entry (EMA cross, MACD, Supertrend) ke upar bolt karte. 3-ATR distance trends ko breathe karne ki room deta while still real reversals pe bail karta.",

  best_market_conditions:
    "Strong sustained trends where you want to capture as much of the move as possible. Daily/weekly trend-following on F&O stocks.",
  worst_market_conditions:
    "Choppy markets — chandelier exits trip too often and you bleed in whipsaws.",

  common_mistakes: [
    "Tightening the multiplier from 3 to 1.5 'to lock in profits' — that's not trailing, that's premature exit.",
    "Using Chandelier as ENTRY — it has no directional signal, only stop placement.",
    "Combining Chandelier with another tight stop — pick ONE exit rule per strategy.",
  ],

  realistic_returns:
    "Chandelier(22, 3) applied to EMA(9/21) crossover entries: increases avg R-multiple from 1.4 to 1.9 (gives winners more room), with a 4-7 percentage point drop in win rate (some winners reverse just enough to trip). Net edge: positive in trending years, neutral in chop. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "HDFC",
    entry: "EMA-cross long at ₹1,650. ATR(22) = ₹22. Initial Chandelier = ₹1,650 - 66 = ₹1,584",
    exit: "Price rises to ₹1,790 over 18 sessions; Chandelier ratchets to ₹1,728. Pullback hits ₹1,728 — exit",
    pnl: "+4.7% per share (₹78). Without trail (just EMA-cross exit), exit would have been ₹1,742 — Chandelier captured an extra ₹14",
  },

  follow_up_strategies: ["ema-crossover-9-21", "supertrend-rider", "macd-trend-signal"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
