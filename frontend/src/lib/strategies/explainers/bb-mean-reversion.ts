import type { StrategyExplainer } from "./_types";

export const BB_MEAN_REVERSION: StrategyExplainer = {
  slug: "bb-mean-reversion",

  what_it_does:
    "Bollinger Bands plot a 20-period SMA flanked by upper and lower bands at 2 standard deviations. Price touching the lower band statistically marks an oversold extreme. We buy when price closes BELOW the lower band, then closes back inside — that recovery is the mean-reversion trigger. Target the middle SMA (a common 'fair value' anchor); exit on touch.\n\nThis is a low-risk, high-frequency setup in sideways markets. The 'price tends to revert toward the mean' assumption is robust in range-bound conditions and broken during trends.",
  what_it_does_hi:
    "Bollinger Bands 20-period SMA plot karta jiske upar-neeche 2 standard deviations pe bands. Price lower band touch karna statistically oversold extreme mark karta. Buy: price lower band ke NEECHE close ho, phir wapas andar close ho — woh recovery mean-reversion trigger. Middle SMA ('fair value' anchor) target karte; touch pe exit.\n\nLow-risk, high-frequency setup sideways markets mein. 'Price mean ki taraf revert karta' assumption range-bound conditions mein robust hai aur trends mein break ho jaata.",

  best_market_conditions:
    "Range-bound consolidations on hourly NIFTY / 15m BANKNIFTY. ADX < 20 confirms the range regime.",
  worst_market_conditions:
    "Strong trends — price 'walks' the lower band for many bars without bouncing. ADX > 25 should suppress all entries.",

  common_mistakes: [
    "Buying at the lower band touch instead of waiting for the close-back-inside confirmation.",
    "Not using ADX < 20 filter — trends absolutely shred this setup.",
    "Setting target beyond the middle band — overshoots happen, but planning for them is curve-fitting against the setup's edge.",
  ],

  realistic_returns:
    "Range-mode mean reversion on Indian large-caps: 58-65% win rate (high), R:R 1:1.2 (low — small targets). Monthly paper at 1% risk: 2-4%. The lower R:R means small losses on bad calls compound quickly if win rate drops.",

  example_trade: {
    symbol: "BANKNIFTY",
    entry: "Price closes below lower BB band, next bar closes back inside, ADX(14) = 16 — long at 47,200",
    exit: "Price reaches middle SMA-20 at 47,350",
    pnl: "+0.32% per unit (150 points). 1 lot (15) at ₹2,000 risk = ~₹2,250 profit",
  },

  follow_up_strategies: ["bb-squeeze-breakout", "bb-rsi-oversold", "bollinger-pct-b-extreme"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
