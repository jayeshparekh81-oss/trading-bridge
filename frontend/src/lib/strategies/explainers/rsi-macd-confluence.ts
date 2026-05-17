import type { StrategyExplainer } from "./_types";

export const RSI_MACD_CONFLUENCE: StrategyExplainer = {
  slug: "rsi-macd-confluence",

  what_it_does:
    "Two independent momentum indicators agreeing on direction is a stronger signal than either one alone. Entry requires: RSI(14) > 50 (bullish momentum confirmed) AND MACD line above its signal AND MACD > 0 (trend regime bullish). Exit when EITHER RSI drops below 50 OR MACD crosses below signal.\n\nThe double-confirmation gate dramatically reduces false signals at the cost of catching trends a few bars late. This is the textbook 'two oscillators agree' pattern and the most robust momentum entry rule for beginners.",
  what_it_does_hi:
    "Do independent momentum indicators direction pe agree karna kisi ek se stronger signal hai. Entry chahiye: RSI(14) > 50 (bullish momentum confirmed) AND MACD line signal ke upar AND MACD > 0 (trend regime bullish). Exit: RSI 50 ke neeche aaye OR MACD signal ke neeche cross kare.\n\nDouble-confirmation gate dramatically false signals reduce karta — cost: trends few bars late catch hote. Textbook 'two oscillators agree' pattern hai aur beginners ke liye most robust momentum entry rule.",

  best_market_conditions:
    "Sustained trends on daily F&O stocks. Post-earnings momentum runs of 5-15 sessions.",
  worst_market_conditions:
    "Choppy markets where RSI and MACD disagree every 2-3 bars. Pre-event consolidation periods.",

  common_mistakes: [
    "Taking entries on partial confluence — if only ONE indicator agrees, it's not 'confluence'.",
    "Setting stops too tight — both indicators lag price; the entry candle's low isn't always the right stop.",
    "Holding through a contrary signal from EITHER indicator — exit on the first one that flips, don't wait for both.",
  ],

  realistic_returns:
    "RSI + MACD confluence on daily F&O stocks: 55-63% win rate (higher than single-indicator setups), R:R 1:1.7. Monthly paper at 1% risk: 3-5%. Fewer trades fire (3-6 per month per stock) but the hit rate is meaningfully higher.",

  example_trade: {
    symbol: "INFY",
    entry: "RSI = 58, MACD = 4.2 (above signal 3.8), MACD > 0 — all confirmed. Long at ₹1,520",
    exit: "MACD crosses below signal nine sessions later at ₹1,605",
    pnl: "+5.6% per share (₹85). Position-sized for ₹2,500 risk = ~30 shares = ₹2,550 profit",
  },

  follow_up_strategies: ["macd-trend-signal", "rsi-oversold-bounce", "macd-divergence"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
