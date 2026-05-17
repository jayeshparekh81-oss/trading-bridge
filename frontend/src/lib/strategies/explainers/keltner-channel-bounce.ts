import type { StrategyExplainer } from "./_types";

export const KELTNER_CHANNEL_BOUNCE: StrategyExplainer = {
  slug: "keltner-channel-bounce",

  what_it_does:
    "Keltner Channels plot an EMA (typically 20-period) with upper/lower bands offset by 2x ATR. Unlike Bollinger Bands (which use standard deviation), Keltner uses ATR — so the bands respond to true range, not just close-to-close volatility. Trade rule: in a clear uptrend (EMA-20 sloping up), buy a pullback to the lower Keltner band; exit at the middle band (the EMA).\n\nThe ATR-based bands are smoother than BB and less prone to false 'band touches' during gap-heavy sessions. Best paired with a trend filter so you only buy pullbacks WITH the trend.",
  what_it_does_hi:
    "Keltner Channels ek EMA (typically 20-period) plot karte upper/lower bands ke saath 2x ATR ke offset pe. Bollinger Bands ke unlike (jo standard deviation use karta), Keltner ATR use karta — to bands true range pe respond karte, sirf close-to-close volatility pe nahi. Trade rule: clear uptrend mein (EMA-20 slope up), lower Keltner band pe pullback pe buy; middle band (EMA) pe exit.\n\nATR-based bands BB se smoother hain aur gap-heavy sessions mein false 'band touches' ke kam prone. Trend filter ke saath best pair hota taki sirf trend ke saath pullbacks buy karo.",

  best_market_conditions:
    "Clear daily uptrends on F&O stocks where price routinely pulls back to the lower Keltner before resuming.",
  worst_market_conditions:
    "Range-bound markets where 'trend' is just noise. Sharp reversal days where price slices through the lower band without pause.",

  common_mistakes: [
    "Buying lower-band touches WITHOUT trend confirmation — in a downtrend, every lower-band buy bleeds.",
    "Setting profit target too far (upper band) — middle band is the realistic mean-reversion target.",
    "Confusing Keltner with Bollinger — they ARE different; Keltner is smoother and tighter in calm markets.",
  ],

  realistic_returns:
    "Keltner lower-band buy with EMA-20 slope-up filter on daily F&O: 56-62% win rate, R:R 1:1.4 (smaller targets). Monthly paper at 1% risk: 3-5%.",

  example_trade: {
    symbol: "SUNPHARMA",
    entry: "EMA-20 sloping up. Price pulls back to lower Keltner band at ₹1,565 — long",
    exit: "Price reaches middle band (EMA-20) at ₹1,610 five sessions later",
    pnl: "+2.9% per share (₹45). Position-sized for ₹2,500 risk = ~55 shares = ₹2,475 profit",
  },

  follow_up_strategies: ["bb-mean-reversion", "vwap-bounce", "ema-crossover-9-21"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
