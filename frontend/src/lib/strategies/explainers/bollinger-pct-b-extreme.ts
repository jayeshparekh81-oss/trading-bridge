import type { StrategyExplainer } from "./_types";

export const BOLLINGER_PCT_B_EXTREME: StrategyExplainer = {
  slug: "bollinger-pct-b-extreme",

  what_it_does:
    "%B normalises price position within the Bollinger Bands to a 0-1 scale: 0 = at lower band, 1 = at upper band, 0.5 = at the middle. When %B prints < 0 (price BELOW lower band — extreme), we enter long expecting reversion to the mean. When %B prints > 1 (above upper band), we short.\n\nThis is the mathematically clean version of 'BB mean reversion' — using %B instead of price gives you a scale-invariant entry trigger that works across stocks at different price levels.",
  what_it_does_hi:
    "%B Bollinger Bands ke andar price position 0-1 scale pe normalise karta: 0 = lower band pe, 1 = upper band pe, 0.5 = middle pe. %B < 0 print kare (price lower band ke NEECHE — extreme) to long enter karte mean reversion expect karte. %B > 1 (upper band ke upar) to short.\n\n'BB mean reversion' ka mathematically clean version hai — price ki jagah %B use karke scale-invariant entry trigger milta jo different price levels ke stocks pe equally work karta.",

  best_market_conditions:
    "Range-bound markets with ADX < 20. Cross-stock screening — sort the universe by %B and trade the extremes daily.",
  worst_market_conditions:
    "Trending markets where %B can sit < 0 or > 1 for many bars. News-driven gap days.",

  common_mistakes: [
    "Treating %B < 0 as guaranteed bounce — in downtrends, %B stays negative for 10+ bars.",
    "Ignoring the BB-width context — %B < 0 with tight bands is different from %B < 0 with wide bands.",
    "Not pairing with a trend filter — %B reversal entries in trending markets bleed money.",
  ],

  realistic_returns:
    "%B < 0 long entries on daily F&O stocks with ADX < 20 filter: 58-65% win rate, R:R 1:1.3. Monthly paper at 1% risk: 2-4%. The ADX filter is critical — without it, win rate drops to ~48%.",

  example_trade: {
    symbol: "TCS",
    entry: "%B = -0.04 (price closes ₹6 below lower BB), ADX = 16 — long at ₹3,560",
    exit: "%B reaches 0.52 (price hits middle band) five sessions later at ₹3,635",
    pnl: "+2.1% per share (₹75). Position-sized for ₹2,000 risk = ~26 shares = ₹1,950 profit",
  },

  follow_up_strategies: ["bb-mean-reversion", "bb-rsi-oversold", "rsi-oversold-bounce"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
