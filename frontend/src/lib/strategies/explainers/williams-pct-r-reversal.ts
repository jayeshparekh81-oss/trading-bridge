import type { StrategyExplainer } from "./_types";

export const WILLIAMS_PCT_R_REVERSAL: StrategyExplainer = {
  slug: "williams-pct-r-reversal",

  what_it_does:
    "Williams %R is the inverted close-position-in-range indicator (scale -100 to 0). %R < -80 = oversold; %R > -20 = overbought. The trade: enter long when %R drops below -80 (deep oversold) and then rises BACK above -80. Exit at %R = -50 (mid-range).\n\nWilliams %R is mathematically very similar to Fast Stochastic but uses a different scale. It's slightly more sensitive than RSI and produces more signals — useful on hourly intraday but noisy on daily without filters.",
  what_it_does_hi:
    "Williams %R inverted close-position-in-range indicator hai (scale -100 to 0). %R < -80 = oversold; %R > -20 = overbought. Trade: long enter karte jab %R -80 ke neeche drop kare (deep oversold) aur phir -80 ke upar WAPAS rise kare. Exit %R = -50 (mid-range) pe.\n\nWilliams %R mathematically Fast Stochastic ke bahut similar hai but different scale use karta. RSI se slightly more sensitive, more signals produce karta — hourly intraday pe useful but daily pe filters ke bina noisy.",

  best_market_conditions:
    "Hourly charts on F&O stocks. Range-bound daily charts with ADX < 20.",
  worst_market_conditions:
    "Trending markets where %R stays < -80 for many bars. Very short timeframes (5-min) where every bar prints a fresh reading.",

  common_mistakes: [
    "Entering on the first %R < -80 reading — extreme readings can persist. Wait for the cross-back above -80.",
    "Using %R = -50 as a profit target in trending markets — in uptrends, %R can stop short of -50 and reverse.",
    "Conflating Williams %R with %B — they look similar on a chart but have different scales and calculations.",
  ],

  realistic_returns:
    "Williams %R cross-back-above-(-80) with ADX < 20 filter on daily F&O: 54-61% win rate, R:R 1:1.4. Monthly paper at 1% risk: 2-4%. Hourly chart variant: 50-57% win rate but ~3x as many setups per month — comparable monthly returns at higher trade count. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "BAJAJ-AUTO",
    entry: "Williams %R = -88 (deep oversold), then crosses back to -76 — long at ₹9,420",
    exit: "%R reaches -50 at ₹9,560 six sessions later",
    pnl: "+1.5% per share (₹140). Position-sized for ₹3,000 risk = ~21 shares = ₹2,940 profit",
  },

  follow_up_strategies: ["stochastic-oscillator", "rsi-oversold-bounce", "mfi-overbought-oversold"],
  difficulty_score: 1,
  capital_efficiency_score: 3,
};
