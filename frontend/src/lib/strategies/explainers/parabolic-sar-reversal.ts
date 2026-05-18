import type { StrategyExplainer } from "./_types";

export const PARABOLIC_SAR_REVERSAL: StrategyExplainer = {
  slug: "parabolic-sar-reversal",

  what_it_does:
    "Parabolic SAR (Stop And Reverse) plots dots above/below price that accelerate toward price each bar. When price crosses through a SAR dot, the dot 'flips' to the other side — that flip is the signal. Long entry: SAR flips from above price to below. Exit/short entry: SAR flips back above.\n\nThe accelerating nature gives PSAR a built-in trailing-stop effect that tightens as the trend matures. It's a complete entry+exit system, but produces too many whipsaws in chop.",
  what_it_does_hi:
    "Parabolic SAR (Stop And Reverse) price ke upar/neeche dots plot karta jo har bar price ki taraf accelerate hote. Jab price kisi SAR dot se cross kare, dot doosri side 'flip' hota — wo flip signal hai. Long entry: SAR price ke upar se neeche flip kare. Exit/short entry: SAR wapas upar flip kare.\n\nAccelerating nature PSAR ko built-in trailing-stop effect deta jo trend mature hone ke saath tighten hota. Complete entry+exit system hai, but chop mein too many whipsaws produce karta.",

  best_market_conditions:
    "Strong trending markets. PSAR shines when it can stay on one side of price for 8-15 sessions without flipping.",
  worst_market_conditions:
    "Choppy markets — PSAR flips every 2-3 bars, churning your account.",

  common_mistakes: [
    "Using PSAR in chop without a trend filter — guaranteed loser.",
    "Adjusting the acceleration factor too aggressively — defaults (0.02 step, 0.2 max) are usually right; tinkering tightens too much.",
    "Treating every PSAR flip as a reversal trade (long → short → long) — that's how you bleed on whipsaws.",
  ],

  realistic_returns:
    "PSAR with ADX > 25 trend filter on daily F&O: 50-58% win rate, R:R 1:1.6. Monthly paper at 1% risk: 3-5%. Without ADX filter: ~40% win rate (chop kills it). Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "TATACONSUM",
    entry: "PSAR flips from above to below price at ₹950, ADX = 26 — long",
    exit: "PSAR flips back above at ₹1,012 ten sessions later",
    pnl: "+6.5% per share (₹62). Position-sized for ₹2,500 risk = ~40 shares = ₹2,480 profit",
  },

  follow_up_strategies: ["adx-strong-trend-filter", "psar-ema-combo", "supertrend-rider"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
