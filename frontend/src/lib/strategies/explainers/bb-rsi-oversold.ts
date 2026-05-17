import type { StrategyExplainer } from "./_types";

export const BB_RSI_OVERSOLD: StrategyExplainer = {
  slug: "bb-rsi-oversold",

  what_it_does:
    "Combines Bollinger Bands' price-position read with RSI's momentum read. Entry requires BOTH: price closes below the lower Bollinger band (extreme price relative to its 20-bar mean) AND RSI < 35 (extreme oversold momentum). Both conditions together filter out single-indicator false signals. Exit at the middle band (mean-reversion target) or RSI > 60.\n\nThis is a stricter version of the basic RSI-oversold setup. By requiring price to ALSO be statistically extreme (sub-band), the entry is much higher conviction — fewer trades, higher win rate.",
  what_it_does_hi:
    "Bollinger Bands ka price-position read aur RSI ka momentum read combine karta. Entry chahiye: price lower Bollinger band ke neeche close ho (apni 20-bar mean ke against extreme price) AND RSI < 35 (extreme oversold momentum). Dono together = single-indicator false signals filter. Exit: middle band (mean-reversion target) ya RSI > 60.\n\nBasic RSI-oversold setup ka stricter version. Price ko ALSO statistically extreme (sub-band) hone require karke entry much higher conviction — fewer trades, higher win rate.",

  best_market_conditions:
    "Range-bound consolidations on daily charts. Pre-event quiet weeks where mean-reversion works cleanly.",
  worst_market_conditions:
    "Strong downtrends — price can stay below the lower band for many bars and RSI < 35 stays.",

  common_mistakes: [
    "Buying at the lower band touch without RSI confirmation — single-indicator setups don't survive in trending markets.",
    "Setting the target too far above the middle band — overshoots are bonuses, not the plan.",
    "Holding through a second lower-band touch — that means trend, not range; exit and reassess.",
  ],

  realistic_returns:
    "BB + RSI confluence on daily large-caps in ADX < 20 regimes: 60-67% win rate, R:R 1:1.3 (small targets). Monthly paper at 1% risk: 2-4%. Lower R:R is the trade-off for higher win rate — losing trades that survive the strict filter are usually trend-onset losses (rare but costly).",

  example_trade: {
    symbol: "TCS",
    entry: "Price closes at ₹3,580 (lower BB at ₹3,595), RSI = 31, ADX = 17. Next bar closes back at ₹3,605 — long",
    exit: "Price reaches middle band at ₹3,665 four sessions later",
    pnl: "+1.7% per share (₹60). Position-sized for ₹2,500 risk = ~42 shares = ₹2,520 profit",
  },

  follow_up_strategies: ["bb-mean-reversion", "bb-squeeze-breakout", "rsi-divergence"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
