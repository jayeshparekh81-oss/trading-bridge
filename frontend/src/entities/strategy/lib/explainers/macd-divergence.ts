import type { StrategyExplainer } from "./_types";

export const MACD_DIVERGENCE: StrategyExplainer = {
  slug: "macd-divergence",

  what_it_does:
    "A bullish MACD divergence: price makes a LOWER low, but MACD makes a HIGHER low at that same time. Translation: even though price went down, downside momentum is weakening. This is one of the most reliable reversal signals in technical analysis when the divergence forms at an established support level.\n\nEntry: on the bullish candle that follows the second (higher-MACD) low. Stop: below the lowest price of the divergence period. The setup is rare but high-conviction.",
  what_it_does_hi:
    "Bullish MACD divergence: price LOWER low banata, but MACD usi time HIGHER low banata. Translation: price neeche gaya bhi to bhi downside momentum weakening hai. Established support level pe divergence form ho to ye technical analysis ke most reliable reversal signals mein se ek.\n\nEntry: bullish candle pe jo second (higher-MACD) low ke baad aaye. Stop: divergence period ke lowest price ke neeche. Setup rare hai but high-conviction.",

  best_market_conditions:
    "Daily charts after extended downtrends (5+ sessions). When the divergence aligns with a known support (50-EMA, prior swing low).",
  worst_market_conditions:
    "Chop where small MACD wiggles get mistaken for divergences. Very short-timeframe charts (5-min/15-min) where divergence is noise.",

  common_mistakes: [
    "Calling 'divergence' on any 2-bar MACD pattern — true divergence needs distinct swing lows separated by enough bars.",
    "Entering at the second low without a confirming candle — divergence alone isn't an entry trigger.",
    "Forgetting the support-level filter — divergence in mid-air (no S/R level) is far weaker than divergence at clear support.",
  ],

  realistic_returns:
    "MACD bullish divergence at support with confirming candle: 56-64% win rate (high for a reversal setup), R:R 1:2.5 (great targets — the prior swing high). Monthly paper at 1% risk: 2-4% — but fires infrequently (2-4 setups per month per stock). Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "ASIANPAINT",
    entry: "Price low ₹3,140 then ₹3,110 (lower); MACD low -8.2 then -6.4 (higher) = bullish divergence at 200-EMA. Confirm candle closes ₹3,135 — long",
    exit: "Profit target at prior swing high ₹3,250 twelve sessions later",
    pnl: "+3.7% per share (₹115). Position-sized for ₹2,500 risk = ~22 shares = ₹2,530 profit",
  },

  follow_up_strategies: ["rsi-divergence", "macd-trend-signal", "macd-histogram-momentum"],
  difficulty_score: 3,
  capital_efficiency_score: 5,
};
