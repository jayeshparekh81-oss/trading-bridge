import type { StrategyExplainer } from "./_types";

export const STOCHASTIC_OSCILLATOR: StrategyExplainer = {
  slug: "stochastic-oscillator",

  what_it_does:
    "Stochastic (%K, %D) measures where the current close sits within the high-low range of the last N bars. %K > 80 = overbought zone; %K < 20 = oversold zone. The classic trade: enter long when %K crosses ABOVE %D AND both are below 20. Exit when %K crosses below %D above 80.\n\nStochastic is more sensitive than RSI (it responds to where the close is within the bar range, not just close-to-close changes), which means more signals but also more whipsaws.",
  what_it_does_hi:
    "Stochastic (%K, %D) measure karta current close last N bars ke high-low range ke andar kahaan baith raha. %K > 80 = overbought zone; %K < 20 = oversold zone. Classic trade: long enter karte jab %K %D ke UPAR cross kare AND dono 20 ke neeche hon. Exit: %K %D ke neeche cross kare 80 ke upar.\n\nStochastic RSI se more sensitive hai (bar range ke andar close kahaan hai us pe respond karta, sirf close-to-close changes pe nahi), to more signals but more whipsaws.",

  best_market_conditions:
    "Range-bound markets with clear support/resistance levels. Pre-event consolidations.",
  worst_market_conditions:
    "Trending markets where stochastic stays > 80 (or < 20) for many bars — 'overbought stays overbought'.",

  common_mistakes: [
    "Taking %K-cross-%D signals OUTSIDE the 20/80 zones — those are mid-range and less reliable.",
    "Using fast stochastic (5, 3, 3) in chop — too noisy; slow stochastic (14, 3, 3) filters better.",
    "Ignoring trend context — overbought in an uptrend is normal; overbought in a range is the signal.",
  ],

  realistic_returns:
    "Slow Stochastic (14,3,3) oversold cross with ADX < 25 filter on daily F&O: 55-62% win rate, R:R 1:1.4. Monthly paper at 1% risk: 2-4%. Without ADX-low filter, stochastic underperforms in trending markets. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "DRREDDY",
    entry: "Stochastic %K = 16, %D = 19. %K crosses above %D both still < 20 — long at ₹5,680",
    exit: "%K crosses below %D above 80 at ₹5,790 eight sessions later",
    pnl: "+1.9% per share (₹110). Position-sized for ₹3,000 risk = ~27 shares = ₹2,970 profit",
  },

  follow_up_strategies: ["rsi-oversold-bounce", "williams-pct-r-reversal", "mfi-overbought-oversold"],
  difficulty_score: 1,
  capital_efficiency_score: 4,
};
