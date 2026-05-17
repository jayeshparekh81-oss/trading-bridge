import type { IndicatorContent } from "./_types";

export const MOMENTUM: IndicatorContent = {
  slug: "momentum",
  name: "Momentum",
  category: "rate",
  complexity: "beginner",

  one_liner_en:
    "Absolute price difference between current close and the close N bars ago. ROC's price-units sibling.",
  one_liner_hi:
    "Current close aur N bars pehle ke close ka absolute price difference. ROC ka price-units sibling hai.",

  description_en:
    "Momentum is the raw price difference between today's close and the close `period` bars ago — no division, no percentage. Output is in price units (rupees for NSE / BSE stocks, points for indices).\n\nROC vs Momentum:\n• ROC = percent change. Comparable across symbols and price levels.\n• Momentum = absolute change. Easier to read against price-axis levels but not cross-symbol comparable.\n\nMomentum is most useful when:\n• You're trading a single symbol and want a direct 'how many points did NIFTY move' read in the indicator's units.\n• You're working with absolute risk targets (e.g. 50-point stops on BANKNIFTY).\n• You're building point-based mean-reversion strategies where the threshold is symbol-specific.\n\nOn its own, Momentum is rarely used as the entry signal in modern strategies — it's overshadowed by ROC (% comparability) and oscillators (bounded). But it's the simplest expression of 'has price gone up or down since N bars ago' and shows up in many composite indicators.",
  description_hi:
    "Momentum aaj ke close aur `period` bars pehle ke close ka raw price difference hai — no division, no percentage. Output price units mein (NSE / BSE stocks ke liye rupees, indices ke liye points).\n\nROC vs Momentum:\n• ROC = percent change. Symbols aur price levels ke across comparable.\n• Momentum = absolute change. Price-axis levels ke against read karna easier but cross-symbol comparable nahi.\n\nMomentum most useful jab:\n• Single symbol trade kar rahe ho aur 'NIFTY kitne points moved' ka direct read indicator units mein chahiye.\n• Absolute risk targets ke saath kaam kar rahe (e.g. BANKNIFTY pe 50-point stops).\n• Point-based mean-reversion strategies bana rahe jahan threshold symbol-specific hai.\n\nApne aap mein Momentum modern strategies mein entry signal ki tarah rarely use hota — ROC (% comparability) aur oscillators (bounded) ne overshadow kar diya. But 'price N bars pehle se up ya down gayi' ka simplest expression hai aur many composite indicators mein dikhta.",

  formula_explanation:
    "Momentum = close - close[period bars ago]. Output is in the symbol's price units. Default period: 10. No smoothing, no normalization. (Some libraries multiply by 100 to make output more readable — verify yours.)",

  default_period: 10,
  period_range: [3, 100],
  common_periods: [10, 14, 20],

  use_cases: [
    {
      scenario: "Single-symbol point-based mean reversion",
      what_to_do: "On NIFTY 1-min, mark when Momentum(10) exceeds ±50 points. Fade extreme readings",
      why: "Point thresholds are concrete and easy to backtest on a single instrument; works only because you've fixed the symbol.",
    },
    {
      scenario: "Composite-indicator input",
      what_to_do: "Use Momentum as the raw input to your own custom smoothing / scaling pipeline",
      why: "Many proprietary momentum indicators start with raw Momentum and apply specific smoothing.",
    },
  ],

  common_signals: [
    {
      signal: "Zero-line cross up",
      condition: "Momentum crosses above 0",
      action: "Bullish bias — price is higher than `period` bars ago.",
    },
    {
      signal: "Zero-line cross down",
      condition: "Momentum crosses below 0",
      action: "Bearish bias.",
    },
    {
      signal: "Divergence",
      condition: "Price new high, Momentum lower high",
      action: "Heads-up for reversal (less common than RSI divergence signals).",
    },
  ],

  pitfalls: [
    "Output is in price units — not cross-symbol comparable. A Momentum of +50 means very different things on a ₹100 stock vs a ₹5000 stock.",
    "No smoothing means raw noise on every bar. Most users prefer ROC or smoothed versions.",
    "Default period varies by source: some libraries default to 10, some 14, some 12. Always specify.",
    "On split-adjusted historical data, momentum values calculated across splits are technically inflated/deflated — usually fine for backtesting but worth knowing.",
  ],

  works_well_with: ["ema", "macd", "adx"],
  works_poorly_with: ["roc", "tsi"],

  example_strategies: [
    "NIFTY Point-Momentum Mean Reversion (1m intraday)",
    "BANKNIFTY Absolute-Move Trend Filter",
  ],

  indian_context:
    "Indian intraday F&O scalpers occasionally use Momentum in point units on NIFTY (50-point threshold) and BANKNIFTY (150-point threshold) for absolute-move setups. The benchmark for 'big move' is asset-specific — what's big on NIFTY 1-min is normal on BANKNIFTY 1-min. ROC is more popular in retail education because percent-comparability makes cross-stock screens straightforward.",
};
