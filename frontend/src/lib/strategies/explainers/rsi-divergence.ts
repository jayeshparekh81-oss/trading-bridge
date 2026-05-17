import type { StrategyExplainer } from "./_types";

export const RSI_DIVERGENCE: StrategyExplainer = {
  slug: "rsi-divergence",

  what_it_does:
    "Bullish RSI divergence: price makes a LOWER low, but RSI makes a HIGHER low. Translation: even though price went down, momentum is weakening — selling pressure is exhausting. Entry: on the bullish candle that follows the second (higher-RSI) low. Stop: below the lowest price of the divergence period.\n\nRSI divergence is the most popular divergence signal in retail trading and has a stronger statistical edge than MACD divergence on shorter timeframes (intraday hourly). On daily timeframes, MACD and RSI divergences perform similarly.",
  what_it_does_hi:
    "Bullish RSI divergence: price LOWER low banaye, RSI HIGHER low banaye. Translation: price neeche gaya bhi to bhi momentum weakening — selling pressure exhausting. Entry: bullish candle pe jo second (higher-RSI) low ke baad aaye. Stop: divergence period ke lowest price ke neeche.\n\nRSI divergence retail trading mein most popular divergence signal hai aur shorter timeframes (intraday hourly) pe MACD divergence se stronger statistical edge rakhta. Daily timeframes pe MACD aur RSI divergences similarly perform karte.",

  best_market_conditions:
    "Hourly/4-hour charts after extended downtrends. Daily charts at established support levels (50/200 EMA, prior swing low).",
  worst_market_conditions:
    "Choppy markets where small RSI wiggles get mistaken for divergences. Very short timeframes (5-min) where divergence is mostly noise.",

  common_mistakes: [
    "Calling 'divergence' on any 2-bar RSI pattern — true divergence needs distinct, separated swing lows.",
    "Trading divergence in isolation — without a confirming candle and a support level, divergence is just a hint.",
    "Entering before the second-low completes — many 'divergences' fail at the right edge as the second low extends.",
  ],

  realistic_returns:
    "RSI bullish divergence at support with confirming candle on daily: 56-63% win rate, R:R 1:2.4 (good targets). Monthly paper at 1% risk: 2-4%. Hourly chart edge is slightly better — RSI is more responsive on shorter timeframes.",

  example_trade: {
    symbol: "AXISBANK",
    entry: "Price low ₹1,040 then ₹1,025 (lower); RSI low 28 then 33 (higher) at 200-EMA. Confirm bullish candle ₹1,042 — long",
    exit: "Profit target at prior swing high ₹1,095 ten sessions later",
    pnl: "+5.1% per share (₹53). Position-sized for ₹2,500 risk = ~30 shares = ₹1,590 profit",
  },

  follow_up_strategies: ["macd-divergence", "obv-divergence", "rsi-oversold-bounce"],
  difficulty_score: 3,
  capital_efficiency_score: 5,
};
