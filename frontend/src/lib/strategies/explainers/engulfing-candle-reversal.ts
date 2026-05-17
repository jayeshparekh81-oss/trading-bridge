import type { StrategyExplainer } from "./_types";

export const ENGULFING_CANDLE_REVERSAL: StrategyExplainer = {
  slug: "engulfing-candle-reversal",

  what_it_does:
    "A bullish engulfing pattern: candle N-1 is red (bearish), candle N is green and its body completely 'engulfs' candle N-1's body (open below N-1 close, close above N-1 open). This is a textbook reversal signal — sentiment flipped meaningfully in one bar.\n\nEntry: on candle N's close (or N+1 open). Stop: below candle N's low. The pattern is most reliable when (a) it occurs at a key support level and (b) candle N closes on volume above the 20-bar average.",
  what_it_does_hi:
    "Bullish engulfing pattern: candle N-1 red (bearish), candle N green aur uska body candle N-1 ka body completely 'engulf' karta (N-1 close ke neeche open, N-1 open ke upar close). Textbook reversal signal — ek bar mein sentiment meaningfully flip ho gaya.\n\nEntry: candle N ke close pe (ya N+1 open). Stop: candle N ke low ke neeche. Pattern most reliable jab (a) key support level pe occur ho aur (b) candle N 20-bar average ke upar volume pe close ho.",

  best_market_conditions:
    "Daily charts at established support levels (50/200 EMA, prior swing low). After 5+ session downtrends where shorts are extended.",
  worst_market_conditions:
    "Mid-trend chop where engulfing patterns form every 4-5 bars. Low-volume sessions (likely manipulation).",

  common_mistakes: [
    "Counting any large green candle after a red as 'engulfing' — the green body MUST fully cover the red body.",
    "Ignoring volume — engulfing on below-average volume is much less reliable.",
    "Stop placement above the engulfing candle's body (not low) — gets stopped on the very test of strength.",
  ],

  realistic_returns:
    "Bullish engulfing at key support with volume confirmation: 55-62% win rate, R:R 1:1.8. Monthly paper at 1% risk: 2-4%. Without the support-level AND volume filters, win rate drops to ~48%.",

  example_trade: {
    symbol: "HCLTECH",
    entry: "Downtrend ending at 50-EMA (₹1,450). Engulfing candle closes at ₹1,478 with volume 1.6x avg — long at close",
    exit: "Profit target (1.8x risk) hit at ₹1,524 seven sessions later",
    pnl: "+3.1% per share (₹46). Position-sized for ₹2,000 risk = ~78 shares = ₹3,590 profit",
  },

  follow_up_strategies: ["hammer-hanging-man-pattern", "doji-reversal", "rsi-oversold-bounce"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
