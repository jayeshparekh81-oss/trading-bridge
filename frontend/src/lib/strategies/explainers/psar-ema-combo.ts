import type { StrategyExplainer } from "./_types";

export const PSAR_EMA_COMBO: StrategyExplainer = {
  slug: "psar-ema-combo",

  what_it_does:
    "Combines Parabolic SAR's flip signal with an EMA-50 trend filter. Long entry requires BOTH: PSAR flips from above to below price AND price closes above EMA-50 (trend regime bullish). Exit: PSAR flips back above price.\n\nThe EMA-50 filter eliminates most of the chop-driven false flips that plague stand-alone PSAR. The trade-off: you'll miss the FIRST flip of a new trend (price often crosses EMA-50 a few bars before the PSAR flip), but you avoid 70% of the noise.",
  what_it_does_hi:
    "Parabolic SAR ke flip signal ko EMA-50 trend filter ke saath combine karta. Long entry chahiye DONO: PSAR price ke upar se neeche flip kare AND price EMA-50 ke upar close ho (trend regime bullish). Exit: PSAR wapas price ke upar flip kare.\n\nEMA-50 filter chop-driven false flips ka majority eliminate karta jo standalone PSAR ko mar dete hain. Trade-off: naye trend ki PEHLI flip miss hogi (price often PSAR flip se kuch bars pehle EMA-50 cross karta), but 70% noise se bachte ho.",

  best_market_conditions:
    "Daily charts of trending F&O stocks. Sector breakouts.",
  worst_market_conditions:
    "Ranging markets where price oscillates around EMA-50. Pre-event consolidation.",

  common_mistakes: [
    "Skipping the EMA-50 filter to 'catch the first flip' — that defeats the entire purpose of the combo.",
    "Using EMA period too short (< 20) — that lets in too much chop; 50 is the sweet spot.",
    "Holding through a PSAR flip 'because price is still above EMA-50' — the exit rule is PSAR flip, period.",
  ],

  realistic_returns:
    "PSAR + EMA-50 combo on daily F&O: 53-60% win rate (10 pp better than PSAR alone), R:R 1:1.7. Monthly paper at 1% risk: 3-5%. The improvement over standalone PSAR is the largest single-filter gain in the trend-following category.",

  example_trade: {
    symbol: "MARUTI",
    entry: "Price closes ₹11,210 (EMA-50 = ₹11,180). PSAR flips below price same day — long",
    exit: "PSAR flips above price at ₹11,580 fourteen sessions later",
    pnl: "+3.3% per share (₹370). Position-sized for ₹3,000 risk = ~8 shares = ₹2,960 profit",
  },

  follow_up_strategies: ["parabolic-sar-reversal", "ema-crossover-9-21", "supertrend-rider"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
