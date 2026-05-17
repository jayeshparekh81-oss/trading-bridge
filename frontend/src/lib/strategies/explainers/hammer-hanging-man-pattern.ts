import type { StrategyExplainer } from "./_types";

export const HAMMER_HANGING_MAN_PATTERN: StrategyExplainer = {
  slug: "hammer-hanging-man-pattern",

  what_it_does:
    "A hammer is a candle with a small body at the top and a long lower shadow (≥ 2x body size) — price was sold down hard intraday but recovered to close near the high. At the END of a downtrend, this is a 'hammer' (bullish reversal). At the END of an uptrend, the same shape is a 'hanging man' (bearish reversal).\n\nEntry: next bar's close confirming the reversal. Stop: below the hammer's low (which is by definition the deepest test of selling).",
  what_it_does_hi:
    "Hammer ek candle hai jiska top pe chhota body aur long lower shadow (≥ 2x body size) — price intraday hard sold down hua but recover karke high ke paas close hua. Downtrend ke END pe ye 'hammer' (bullish reversal). Uptrend ke END pe same shape 'hanging man' (bearish reversal).\n\nEntry: next bar ka close reversal confirm kare. Stop: hammer ke low ke neeche (jo definition se selling ka deepest test hai).",

  best_market_conditions:
    "Daily charts at established support levels. After 4+ session downtrends. Earnings sell-off bottoms.",
  worst_market_conditions:
    "Mid-trend chop where hammer-shaped candles form every 5-6 bars meaning nothing. Low-volume sessions.",

  common_mistakes: [
    "Calling any candle with a lower shadow a hammer — the shadow must be ≥ 2x the body to qualify.",
    "Trading the hammer in isolation — context (downtrend, support level) is what makes it meaningful.",
    "No next-bar confirmation — raw hammers without confirming bar are ~50/50.",
  ],

  realistic_returns:
    "Hammer with next-bar confirmation at support: 54-61% win rate, R:R 1:1.7. Monthly paper at 1% risk: 2-4%. Without next-bar AND support-level filters, win rate drops to ~47%.",

  example_trade: {
    symbol: "WIPRO",
    entry: "Downtrend from ₹560 to ₹520 over 5 days. Hammer at ₹520 (body ₹3, lower shadow ₹8). Next bar closes ₹524 — long",
    exit: "Target 1.7x risk hit at ₹533 four sessions later",
    pnl: "+1.7% per share (₹9). Position-sized for ₹2,000 risk = ~400 shares = ₹3,600 profit",
  },

  follow_up_strategies: ["doji-reversal", "engulfing-candle-reversal", "rsi-oversold-bounce"],
  difficulty_score: 2,
  capital_efficiency_score: 3,
};
