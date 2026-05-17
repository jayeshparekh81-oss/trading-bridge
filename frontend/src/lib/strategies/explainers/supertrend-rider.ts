import type { StrategyExplainer } from "./_types";

export const SUPERTREND_RIDER: StrategyExplainer = {
  slug: "supertrend-rider",

  what_it_does:
    "Supertrend is an ATR-based line that flips between 'bullish' (green, plotted below price) and 'bearish' (red, plotted above price). We enter long on a fresh green flip and use the Supertrend line itself as a trailing stop. Exit when Supertrend flips back to red.\n\nThis is the single most popular indicator in Indian retail F&O — for good reason. It's binary (long or flat, no ambiguity), volatility-aware (the trail loosens automatically on volatile bars), and visually obvious. The trade-off: in chop, Supertrend flips constantly and produces small consecutive losses.",
  what_it_does_hi:
    "Supertrend ek ATR-based line hai jo 'bullish' (green, price ke neeche plotted) aur 'bearish' (red, price ke upar plotted) ke beech flip karti. Fresh green flip pe long enter karte aur Supertrend line ko khud trailing stop ki tarah use karte. Supertrend wapas red flip kare to exit.\n\nIndian retail F&O ka single most popular indicator — accha reason ke saath. Binary hai (long ya flat, no ambiguity), volatility-aware (trail volatile bars pe automatically loose), aur visually obvious. Trade-off: chop mein Supertrend constantly flip karta aur small consecutive losses produce karta.",

  best_market_conditions:
    "Trending markets — daily charts of NSE F&O stocks during sector rotation, 15-minute BANKNIFTY on directional days. ADX > 25 confirms quality.",
  worst_market_conditions:
    "Sideways markets where Supertrend flips every few bars (death by a thousand cuts). Indian budget-week mornings often have a fake flip in the first 30 minutes.",

  common_mistakes: [
    "Using ATR multiplier 1.5 instead of default 3 because 'I want faster signals' — that just multiplies flip frequency in chop.",
    "Trading every flip without an ADX filter — chop will eat you alive.",
    "Holding past a flip 'because the bar might still recover' — the flip IS the exit signal; respect it.",
  ],

  realistic_returns:
    "Daily Supertrend with ADX > 20 filter on Indian F&O stocks: 52-60% win rate, R:R 1:1.7. Monthly paper-mode return at 1% risk: 3-6%. The single biggest improvement-per-effort win on this strategy is adding the ADX filter; without it returns drop to 0-2%.",

  example_trade: {
    symbol: "INFY",
    entry: "Supertrend flips green on daily, ADX(14) = 26 — long at ₹1,490",
    exit: "Supertrend flips red eleven sessions later at ₹1,558",
    pnl: "+4.6% per share (₹68). Position-sized for ₹2,500 risk = ~36 shares = ₹2,450 profit",
  },

  follow_up_strategies: ["adx-strong-trend-filter", "psar-ema-combo", "chandelier-exit-trail"],
  difficulty_score: 1,
  capital_efficiency_score: 4,
};
