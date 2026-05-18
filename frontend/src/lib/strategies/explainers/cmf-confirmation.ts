import type { StrategyExplainer } from "./_types";

export const CMF_CONFIRMATION: StrategyExplainer = {
  slug: "cmf-confirmation",

  what_it_does:
    "Chaikin Money Flow (CMF) measures buying vs selling pressure by combining price position within each bar's range with volume. CMF > 0 means net accumulation; CMF < 0 means distribution. We use CMF purely as a CONFIRMATION filter on long entries — only take a long if the price-based setup AND CMF > 0.05 (clear accumulation).\n\nWhy it works: price moves can be 'low-quality' (low volume) and reverse quickly. CMF separates rallies driven by real buying from rallies driven by short-covering or thin tape.",
  what_it_does_hi:
    "Chaikin Money Flow (CMF) buying vs selling pressure measure karta — har bar ke range ke andar price position + volume combine karke. CMF > 0 = net accumulation; CMF < 0 = distribution. Hum CMF purely CONFIRMATION filter ki tarah use karte long entries pe — long tabhi lo jab price-based setup AND CMF > 0.05 (clear accumulation).\n\nKyun kaam karta: price moves 'low-quality' (low volume) ho sakte aur quickly reverse. CMF real buying se driven rallies ko short-covering ya thin tape se driven rallies se separate karta.",

  best_market_conditions:
    "Use on any equity long-entry setup where volume matters — breakouts, gap-fills, oversold bounces. Most useful on cash-segment stocks (not as useful on index futures).",
  worst_market_conditions:
    "Index F&O where CMF readings are diluted by hedging flow. Low-volume small caps where any CMF reading is statistically noisy.",

  common_mistakes: [
    "Using CMF as an entry signal — it's a confirmation filter only. CMF > 0.05 by itself doesn't tell you WHERE to buy.",
    "Threshold too loose (CMF > 0) — anything between -0.05 and +0.05 is noise; require ±0.05 minimum.",
    "Applying CMF filter on index F&O without adjustment — index CMF rarely exceeds ±0.1.",
  ],

  realistic_returns:
    "CMF > 0.05 confirmation filter applied to RSI-oversold bounce setup on equity longs: +6-9 percentage point win-rate lift (from ~52% to ~60%). Monthly paper at 1% risk: +1-2 percentage points vs no filter. Most useful on mid-cap stocks. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "TATAMOTORS",
    entry: "RSI = 31 (oversold bounce setup), CMF = 0.09 (strong accumulation) — long at ₹780",
    exit: "RSI > 60 at ₹830 six sessions later",
    pnl: "+6.4% per share (₹50). Position-sized for ₹2,500 risk = ~50 shares = ₹2,500 profit",
  },

  follow_up_strategies: ["rsi-oversold-bounce", "volume-spike-price-confirm", "obv-divergence"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
