import type { StrategyExplainer } from "./_types";

export const EMA_CROSSOVER_9_21: StrategyExplainer = {
  slug: "ema-crossover-9-21",

  what_it_does:
    "This is the classic 'two moving averages crossing each other' trade. We plot a 9-bar EMA (fast) and a 21-bar EMA (slow). When the fast one crosses ABOVE the slow one, the short-term price is moving faster than the medium-term price — interpreted as the trend turning bullish, so we go long. The reverse cross (9 falling below 21) marks the turn back down, so we exit.\n\nThe edge is simple: in genuine trends, the fast EMA leads the slow one and crosses produce real signals. The cost: in sideways markets, the two EMAs cross each other every few bars and every cross is a fake-out. Trend-following crossovers shine in markets that are actually trending and lose money in markets that aren't.",
  what_it_does_hi:
    "Yeh classic 'do moving averages cross karna' wala trade hai. 9-bar EMA (fast) aur 21-bar EMA (slow) plot karte. Fast wali slow wali ke UPAR cross kare — short-term price medium-term se fast move kar rahi — trend bullish ho rahi, isliye long jaate. Ulta cross (9 21 ke neeche) turn back down mark karta, isliye exit.\n\nEdge simple hai: genuine trends mein fast EMA slow ko lead karti aur crosses real signals dete. Cost: sideways markets mein dono EMAs har kuch bars mein cross karti aur har cross fake-out hota. Trend-following crossovers actually trending markets mein shine karte aur non-trending markets mein paise lose karte.",

  best_market_conditions:
    "Trending markets with rising ADX > 20. Daily charts of large-cap F&O stocks during clear sector rotations. Post-earnings momentum runs.",
  worst_market_conditions:
    "Range-bound consolidations (NIFTY pre-budget weeks, expiry days, low-volatility holiday sessions). ADX < 15 = consistently lossy whipsaws.",

  common_mistakes: [
    "Taking every cross without an ADX or volume filter — most crosses in any given month are chop.",
    "Setting stops too tight (less than 1× ATR) so normal pullbacks knock you out before the trend resumes.",
    "Doubling down after a losing cross to 'recover faster' — that's how 10% drawdowns become 30%.",
  ],

  realistic_returns:
    "On Indian large-cap daily charts with proper filtering (ADX > 20), historical win rate hovers around 45-55%. Average R:R 1:1.5. Realistic monthly paper-mode return at sensible 1% risk-per-trade sizing: 2-5%. Returns above 8%/month sustained should make you suspicious of curve-fit results. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "RELIANCE",
    entry: "EMA-9 crosses above EMA-21 with ADX(14) at 22, price above 50-EMA — long at ₹2,850",
    exit: "EMA-9 crosses below EMA-21 six sessions later at ₹2,920",
    pnl: "+2.4% per share (₹70). Position-sized for ₹2,000 risk = ~30 shares = ₹2,100 profit",
  },

  follow_up_strategies: ["adx-strong-trend-filter", "supertrend-rider", "triple-ema-crossover"],
  difficulty_score: 2,
  capital_efficiency_score: 3,
};
