import type { IndicatorContent } from "./_types";

export const STANDARD_DEVIATION: IndicatorContent = {
  slug: "standard-deviation",
  name: "Standard Deviation",
  category: "volatility",
  complexity: "intermediate",

  one_liner_en:
    "Statistical measure of how far prices spread from their average. The volatility math under Bollinger Bands.",
  one_liner_hi:
    "Statistical measure ki prices apne average se kitna spread hain. Bollinger Bands ke neeche ki volatility math.",

  description_en:
    "Standard deviation (σ) is the textbook statistical measure of dispersion: take the differences between each close and the SMA, square them, average the squared differences, and take the square root. The result is in price units and tells you the 'typical' deviation from the mean.\n\nAs a standalone indicator (plotted in its own panel) standard deviation reads as a volatility regime gauge. Rising σ = volatility expanding; falling σ = volatility contracting. Unlike ATR, it doesn't include intra-bar high-low ranges — only close-to-mean deviations — so it can underestimate volatility on days with big intraday swings but quiet closes.\n\nMost retail users encounter standard deviation indirectly: Bollinger Bands' width is `mult × σ`, Z-score is `(close - mean) / σ`, statistical mean-reversion bands all use σ. Knowing what σ is helps you read those derived indicators more competently.\n\nA practical use: spot 'volatility breakouts' — σ rising from a low base often precedes large directional moves. Pair with direction signals (MACD, EMA-slope) to time the entry.",
  description_hi:
    "Standard deviation (σ) dispersion ka textbook statistical measure hai: har close aur SMA ke beech ka difference lo, square karo, squared differences ka average lo, square root lo. Result price units mein hai aur 'typical' deviation from mean batata.\n\nStandalone indicator (apne panel mein plot) ki tarah standard deviation volatility regime gauge ki tarah reads karta. Rising σ = volatility expand ho rahi; falling σ = contract. ATR ke unlike, intra-bar high-low ranges include nahi karta — sirf close-to-mean deviations — isliye big intraday swings but quiet closes wale days pe volatility underestimate kar sakta.\n\nMost retail users σ ko indirectly meet karte hain: Bollinger Bands' width `mult × σ` hai, Z-score `(close - mean) / σ`, statistical mean-reversion bands sab σ use karte hain. σ kya hai pata hone se derived indicators ko competently read kar sakte ho.\n\nPractical use: 'volatility breakouts' spot karna — low base se σ rising often large directional moves se pehle hota hai. Direction signals (MACD, EMA-slope) ke saath pair karke entry time karo.",

  formula_explanation:
    "σ = sqrt(mean((close - SMA)²)) over `period` bars. Biased version (divisor N) is the platform default in Pine Script and pandas-ta-classic; sample version (divisor N-1) is the statistics textbook default. The two differ by sqrt(N / (N-1)) — at period 20, ~2.6%. Default period: 20.",

  default_period: 20,
  period_range: [5, 100],
  common_periods: [10, 20, 50],

  use_cases: [
    {
      scenario: "Volatility-regime gauge",
      what_to_do: "Plot σ in a sub-panel. Mark when σ crosses above its own 50-period average — that's a volatility expansion signal",
      why: "Volatility clusters — once it expands, it tends to stay expanded for a while. Trading on a fresh expansion signal gives wider stops + larger moves.",
            },
    {
      scenario: "Bollinger-Bands-decomposition for tuning",
      what_to_do: "If you find Bollinger Bands too tight on a stock, raise the σ multiplier from 2 to 2.5",
      why: "Understanding that bands are σ × multiplier makes the tuning intentional rather than guess-and-check.",
    },
    {
      scenario: "Z-score mean reversion",
      what_to_do: "Compute (close - SMA) / σ; values above +2 are extreme highs, below -2 are extreme lows; mean-revert toward 0",
      why: "Z-score is the cleanest dimensionless mean-reversion metric — works across symbols and price levels.",
    },
  ],

  common_signals: [
    {
      signal: "Volatility expansion",
      condition: "σ crosses above its own moving average",
      action: "Volatility regime change — widen stops, prepare for bigger moves.",
    },
    {
      signal: "Volatility compression",
      condition: "σ falls to multi-week lows",
      action: "Range-trading window; squeeze breakout likely soon.",
    },
  ],

  pitfalls: [
    "Biased vs sample σ differ by a few percent. Match the convention your charting tool uses or live values will deviate from backtest.",
    "Underestimates 'real' volatility on days with large intraday range but quiet close — ATR captures this better.",
    "Statistical formula assumes near-normal distribution; markets have fat tails. σ × 2 captures less than the textbook 95% of moves.",
    "On gap days, σ spikes for several bars as the gap close is far from the mean — distortion lasts ~period bars.",
    "Period choice matters a lot — short periods are twitchy, long periods are slow.",
  ],

  works_well_with: ["bollinger-bands", "atr", "ema", "vwap"],
  works_poorly_with: ["keltner-channel", "donchian-channel"],

  example_strategies: [
    "Z-Score Mean Reversion (intraday F&O)",
    "Volatility-Expansion Breakout (daily indices)",
    "σ-Tuned Bollinger Bands (per-symbol)",
  ],

  indian_context:
    "Standard deviation on NIFTY daily closes hovers around 0.6-0.9% in calm periods, spikes to 1.5-2.5% during budget / RBI policy / global-event days. BANKNIFTY's σ is roughly 50% higher in absolute terms — comparing 'NIFTY σ' to 'BANKNIFTY σ' directly is misleading. For F&O stocks during earnings season, σ doubles in the 5 sessions around results; a σ that doubles before results is a quantifiable 'event-positioned' signal. The biased vs sample distinction matters less in Indian retail than in academic research — most local tools use the biased default.",
};
