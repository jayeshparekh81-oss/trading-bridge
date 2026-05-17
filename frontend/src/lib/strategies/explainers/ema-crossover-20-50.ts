import type { StrategyExplainer } from "./_types";

export const EMA_CROSSOVER_20_50: StrategyExplainer = {
  slug: "ema-crossover-20-50",

  what_it_does:
    "The slower cousin of EMA-9/21. We watch the 20-bar EMA crossing the 50-bar EMA. Because both averages are slower, signals fire less often but each cross marks a more meaningful trend regime change. This is a swing-trading setup, not a scalp.\n\nEntries trigger when the 20 crosses above 50 (bullish regime); exits when it crosses below. The slower pair filters out most intraday and short-term noise — at the cost of catching the start of a trend late. On daily charts of NSE-50 stocks, a fresh 20/50 cross is usually a 'this stock has structurally turned' signal.",
  what_it_does_hi:
    "EMA-9/21 ka slow cousin. 20-bar EMA 50-bar EMA ko cross karte dekhte. Dono averages slow hain isliye signals less often fire hote but har cross zyada meaningful trend regime change mark karta. Swing-trading setup hai, scalp nahi.\n\nEntries: 20 50 ke upar cross (bullish regime); exits: neeche cross. Slow pair most intraday + short-term noise filter karta — cost: trend ka start late catch hota. Daily charts NSE-50 stocks pe fresh 20/50 cross usually 'stock structurally turn ho gaya' signal hai.",

  best_market_conditions:
    "Daily timeframe on NSE-100 large caps in defined macro trends (post-budget rallies, sector-rotation cycles). Weekly chart for positional swing trades.",
  worst_market_conditions:
    "Choppy 2-3 month sideways markets where 20 and 50 are tangled together. Crossovers in those regimes mean nothing.",

  common_mistakes: [
    "Using 20/50 cross on intraday — the lag is too large; the trend has often run by the time you enter.",
    "Ignoring the slope: a 20-cross-above-50 with both lines sloping down is a counter-trend signal, not a regime change.",
    "Holding through a contrary cross hoping 'it'll come back' — the cross is the regime signal; respect it.",
  ],

  realistic_returns:
    "Daily-chart historical edge on Indian large-caps: 50-58% win rate, R:R 1:2 average. Slow-fires (4-8 trades/year per stock). Monthly returns at 1% risk: 1-3% — slower than 9/21 but with fewer drawdown shocks. Best for traders with day jobs who check positions once daily.",

  example_trade: {
    symbol: "TCS",
    entry: "EMA-20 crosses above EMA-50 on daily, ADX rising — long at ₹3,640",
    exit: "EMA-20 crosses below EMA-50 forty-two sessions later at ₹3,880",
    pnl: "+6.6% per share (₹240). Position-sized for ₹2,500 risk = ~10 shares = ₹2,400 profit",
  },

  follow_up_strategies: ["adx-strong-trend-filter", "supertrend-rider", "chandelier-exit-trail"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
