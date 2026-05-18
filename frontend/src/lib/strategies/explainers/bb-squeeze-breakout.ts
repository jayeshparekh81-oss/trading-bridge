import type { StrategyExplainer } from "./_types";

export const BB_SQUEEZE_BREAKOUT: StrategyExplainer = {
  slug: "bb-squeeze-breakout",

  what_it_does:
    "When Bollinger Bands contract tightly (low volatility), the market is 'coiling'. Statistically, big directional moves follow such squeezes. We measure the band width and wait for it to reach a multi-week low; then enter on whichever direction price first breaks out of the squeeze. Stops just past the opposite side of the squeeze range.\n\nThe trade-off: you don't know the breakout direction in advance, so half the trades fail (squeeze breaks UP becomes a fakeout that immediately drops). The other half catch the big move that pays for the failures and then some.",
  what_it_does_hi:
    "Bollinger Bands tightly contract (low volatility) hone pe market 'coil' kar raha hota. Statistically, aise squeezes ke baad bade directional moves aate. Band width measure karte aur multi-week low tak pahunchne ka wait karte; phir price jis direction squeeze se pehle break kare, us direction mein enter. Stops squeeze range ke opposite side ke just past.\n\nTrade-off: breakout direction advance mein nahi pata, isliye aadhi trades fail hoti (squeeze UP break = fakeout jo turant girta). Doosri aadhi big move catch karti jo failures aur kuch extra pay karti.",

  best_market_conditions:
    "Daily charts of NSE F&O stocks after extended consolidations. Pre-earnings squeezes are particularly clean.",
  worst_market_conditions:
    "Already-trending markets (no squeeze present). High-volatility regimes where bands rarely contract.",

  common_mistakes: [
    "Front-running the squeeze — entering before price actually breaks out. Wait for the close beyond.",
    "Setting stops too far away (more than 1 ATR) — squeeze trades' edge depends on tight risk.",
    "Holding the failed first breakout direction when price reverses — the squeeze can fire BOTH ways within the same week.",
  ],

  realistic_returns:
    "Squeeze breakouts on daily F&O stocks: 40-50% win rate (low) but R:R 1:3 on average — high asymmetry. Monthly paper at 1% risk: 3-7% with high variance. Best as part of a multi-strategy portfolio because the cadence is lumpy. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "RELIANCE",
    entry: "Bollinger bandwidth at 6-week low, price breaks above upper band — long at ₹2,910",
    exit: "Profit target (3 ATR move) hit ten sessions later at ₹3,015",
    pnl: "+3.6% per share (₹105). Position-sized for ₹2,500 risk = ~24 shares = ₹2,520 profit",
  },

  follow_up_strategies: ["squeeze-momentum", "donchian-channel-breakout", "bb-mean-reversion"],
  difficulty_score: 3,
  capital_efficiency_score: 4,
};
