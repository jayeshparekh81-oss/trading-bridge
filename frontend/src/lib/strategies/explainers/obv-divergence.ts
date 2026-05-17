import type { StrategyExplainer } from "./_types";

export const OBV_DIVERGENCE: StrategyExplainer = {
  slug: "obv-divergence",

  what_it_does:
    "On-Balance Volume (OBV) is a cumulative running total — add volume on up-days, subtract volume on down-days. OBV measures accumulation/distribution over time. A bullish OBV divergence: price makes a LOWER low while OBV makes a HIGHER low. Translation: even though price went down, net buying volume rose — smart money is quietly accumulating.\n\nEntry: on the bullish candle that follows the second (OBV-higher) low. Stop: below the lowest price of the divergence period. Similar setup to MACD divergence but uses volume instead of momentum.",
  what_it_does_hi:
    "On-Balance Volume (OBV) cumulative running total hai — up-days pe volume add, down-days pe subtract. OBV time ke saath accumulation/distribution measure karta. Bullish OBV divergence: price LOWER low banaye, OBV HIGHER low banaye. Translation: price neeche gaya bhi to bhi net buying volume rose — smart money quietly accumulate kar rahe.\n\nEntry: bullish candle pe jo second (OBV-higher) low ke baad aaye. Stop: divergence period ke lowest price ke neeche. MACD divergence ke similar but momentum ki jagah volume use karta.",

  best_market_conditions:
    "Daily charts of equity cash stocks. Sector rotation environments where institutional flow is rotating in/out.",
  worst_market_conditions:
    "Index F&O (volume includes hedging). Low-volume small caps (OBV is noise). Very short-timeframe charts.",

  common_mistakes: [
    "Trading OBV divergence without a confirming candle — divergence is a setup, the candle is the trigger.",
    "Calling 'divergence' on small OBV wiggles — true divergence needs distinct, visible swing lows.",
    "Using OBV divergence on F&O — F&O volume is contaminated by hedging; OBV works much better on cash equity.",
  ],

  realistic_returns:
    "OBV bullish divergence on equity cash daily with confirming candle: 54-61% win rate, R:R 1:2.3 (good targets — prior swing high). Monthly paper at 1% risk: 2-4%. Like MACD divergence, fires infrequently.",

  example_trade: {
    symbol: "TATAPOWER",
    entry: "Price low ₹385 then ₹378 (lower); OBV rising during this period (higher) = bullish divergence. Confirm bullish candle ₹382 — long",
    exit: "Profit target at prior swing high ₹407 eleven sessions later",
    pnl: "+6.5% per share (₹25). Position-sized for ₹2,000 risk = ~80 shares = ₹2,000 profit",
  },

  follow_up_strategies: ["macd-divergence", "rsi-divergence", "cmf-confirmation"],
  difficulty_score: 3,
  capital_efficiency_score: 5,
};
