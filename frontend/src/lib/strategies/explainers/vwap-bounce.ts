import type { StrategyExplainer } from "./_types";

export const VWAP_BOUNCE: StrategyExplainer = {
  slug: "vwap-bounce",

  what_it_does:
    "VWAP (Volume Weighted Average Price) is the session's running 'fair price'. Institutions try to buy below VWAP and sell above it — making VWAP a real intraday support/resistance line. When price pulls back to VWAP from above in an uptrend and prints a bullish candle, that's our entry — institutions are stepping in. Exit at the day's prior high or at session close.\n\nThe edge: VWAP is the single most-watched intraday reference. The cost: VWAP loses informativeness in the last 90 minutes of an expiry day when OI unwinding distorts trade flow.",
  what_it_does_hi:
    "VWAP (Volume Weighted Average Price) session ka running 'fair price' hai. Institutions VWAP ke neeche buy aur upar sell karne ki koshish karte — VWAP ko real intraday support/resistance line bana deta. Uptrend mein price upar se VWAP tak pull back kare aur bullish candle print kare — entry — institutions step in kar rahe. Exit day's prior high ya session close pe.\n\nEdge: VWAP single most-watched intraday reference. Cost: expiry day ke last 90 minutes mein OI unwinding trade flow distort karta to VWAP informativeness khoti.",

  best_market_conditions:
    "Trending intraday days with steady volume. NIFTY / BANKNIFTY first 90 minutes (09:15-10:45 IST) often deliver clean VWAP pullbacks.",
  worst_market_conditions:
    "Expiry day's last hour. Volatile event-driven days. Sideways days where price oscillates around VWAP all day.",

  common_mistakes: [
    "Buying the FIRST VWAP touch — wait for the bullish candle confirmation; touches without confirmation often pierce through.",
    "Holding overnight — VWAP resets daily; the setup is intraday-only.",
    "Trading VWAP on options instead of cash/futures — option pricing reacts to Greeks, not directly to VWAP.",
  ],

  realistic_returns:
    "VWAP pullback on NIFTY F&O during 09:30-13:00 IST window: 52-60% win rate, R:R 1:1.6. Monthly paper at 1% risk: 3-5%. Strongest in first 90 minutes; degrades through the session.",

  example_trade: {
    symbol: "NIFTY",
    entry: "Uptrend on 5-min, price pulls back from 22,300 to VWAP at 22,240, bullish hammer prints — long at 22,250",
    exit: "Profit target (prior session high at 22,310) hit 40 minutes later",
    pnl: "+0.27% per unit (60 points). 1 lot (50) for ₹1,500 risk = ~₹3,000 profit",
  },

  follow_up_strategies: ["orb-15min", "volume-spike-price-confirm", "pivot-point-bounce"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
