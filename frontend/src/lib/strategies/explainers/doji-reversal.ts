import type { StrategyExplainer } from "./_types";

export const DOJI_REVERSAL: StrategyExplainer = {
  slug: "doji-reversal",

  what_it_does:
    "A doji candle (open ≈ close, with shadows in both directions) signals indecision at the close of a directional move. We enter on the NEXT candle's confirmation: after a downtrend ending in a doji, enter long on the next candle's close above the doji's high. Stop goes below the doji's low.\n\nDojis are the classic 'momentum exhaustion' signal in candlestick analysis. The next-bar confirmation requirement filters out random dojis from genuine reversal setups.",
  what_it_does_hi:
    "Doji candle (open ≈ close, dono directions mein shadows) directional move ke close pe indecision signal karta. Hum NEXT candle ki confirmation pe enter karte: downtrend doji pe end hone ke baad, next candle ka close doji ke high ke upar ho to long enter. Stop doji ke low ke neeche.\n\nDojis candlestick analysis ka classic 'momentum exhaustion' signal. Next-bar confirmation requirement random dojis ko genuine reversal setups se filter karta.",

  best_market_conditions:
    "Daily charts at key support levels (50-EMA, prior swing low, round numbers). Stocks in clear downtrend that's been running 5+ sessions.",
  worst_market_conditions:
    "Choppy sideways markets where dojis form every 3-4 bars meaning nothing. Pre-event consolidation.",

  common_mistakes: [
    "Entering on the doji candle itself — wait for next-bar confirmation; raw dojis are ~50/50.",
    "Ignoring the prior trend context — a doji in chop is meaningless; a doji after a 5-day move is the signal.",
    "Stop too tight (below doji's body, not below shadow) — that exits on the very confirmation move you wanted.",
  ],

  realistic_returns:
    "Doji reversal with next-bar confirmation at key support levels: 53-60% win rate, R:R 1:1.6. Monthly paper at 1% risk: 2-4%. Without next-bar confirmation, win rate drops to ~46% (raw dojis are noise). Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "SBIN",
    entry: "Downtrend from ₹820 to ₹775 (5 days). Doji at ₹775 (high 779, low 772). Next candle closes at ₹782 — long",
    exit: "Profit target (1.6x risk) at ₹793 four sessions later",
    pnl: "+1.4% per share (₹11). Position-sized for ₹2,000 risk = ~285 shares = ₹3,135 profit",
  },

  follow_up_strategies: ["hammer-hanging-man-pattern", "engulfing-candle-reversal", "inside-bar-breakout"],
  difficulty_score: 2,
  capital_efficiency_score: 3,
};
