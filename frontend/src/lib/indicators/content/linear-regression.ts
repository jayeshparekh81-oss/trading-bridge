import type { IndicatorContent } from "./_types";

export const LINEAR_REGRESSION: IndicatorContent = {
  slug: "linear-regression",
  name: "Linear Regression (Linreg Slope)",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "Best-fit straight line over the last N bars, plus its slope. Math-grounded trend direction + steepness measure.",
  one_liner_hi:
    "Last N bars ki best-fit straight line, plus uska slope. Math-grounded trend direction + steepness measure.",

  description_en:
    "Linear regression fits the least-squares-best straight line through the closing prices of the last `period` bars. Two outputs are common: the line's endpoint (sometimes plotted as a moving 'LRMA') and its slope. The slope is the more informative read — it directly quantifies trend direction and steepness in price-units-per-bar.\n\nPositive slope = uptrend; negative = downtrend; near-zero = sideways. The MAGNITUDE of the slope tells you trend steepness, which RSI and Stochastic don't.\n\nLinreg slope is well-suited as a trend filter precisely because it's a clean math measure — no ad-hoc constants like EMA's α or ADX's 0.015 multiplier. Slope crossing through zero is a clean trend-regime change signal; slope sustained well above zero is a confirmed up-trend.\n\nSome libraries also expose 'Linreg Curve' (the endpoint plotted over time) — which functions like an alternative-formula MA. Combined with the slope, it gives a complete trend read in two numbers.",
  description_hi:
    "Linear regression last `period` bars ke closing prices ke through least-squares-best straight line fit karta. Do outputs common hain: line ka endpoint (kabhi 'LRMA' moving average ki tarah plot) aur uska slope. Slope zyada informative read — directly trend direction aur steepness ko price-units-per-bar mein quantify karta.\n\nPositive slope = uptrend; negative = downtrend; near-zero = sideways. Slope ki MAGNITUDE trend steepness batati, jo RSI aur Stochastic nahi batate.\n\nLinreg slope trend filter ki tarah well-suited hai precisely clean math measure hone ki wajah se — no ad-hoc constants jaise EMA ka α ya ADX ka 0.015 multiplier. Slope zero ke through cross karna clean trend-regime change signal; slope sustained well above zero confirmed up-trend.\n\nKuch libraries 'Linreg Curve' bhi expose karti hain (endpoint over time plotted) — jo alternative-formula MA ki tarah function karta. Slope ke saath combine = complete trend read in two numbers.",

  formula_explanation:
    "Over `period` bars, fit slope m and intercept b to minimise sum((close[i] - (m × i + b))²). m is the slope (price units per bar); b is the y-intercept. Endpoint = m × (period - 1) + b. Default period: 14.",

  default_period: 14,
  period_range: [5, 100],
  common_periods: [10, 14, 20, 50],

  use_cases: [
    {
      scenario: "Mathematically rigorous trend filter",
      what_to_do: "Long bias only when 50-bar linreg slope > 0",
      why: "Cleaner than EMA-slope because linreg minimises squared-error fit — gives a math-justified directionality read.",
    },
    {
      scenario: "Cross-symbol trend strength ranking",
      what_to_do: "Compute normalised slope (slope / price) across a watchlist; rank descending; top decile = strongest uptrends",
      why: "Normalised slope is cross-symbol comparable (unlike absolute MACD or unbounded CCI). Useful for screening.",
    },
  ],

  common_signals: [
    {
      signal: "Slope crosses zero (up)",
      condition: "Linreg slope crosses above 0",
      action: "Bullish trend regime — enable long-only strategies.",
    },
    {
      signal: "Slope acceleration",
      condition: "Slope rising while remaining positive",
      action: "Trend strengthening — hold and add on pullbacks.",
    },
  ],

  pitfalls: [
    "Linear regression assumes a STRAIGHT line. Curved trends (parabolic moves) are fit poorly — slope reads can mislead.",
    "Short periods (<10) make linreg extremely twitchy — every bar's local noise affects the fit.",
    "Absolute slope values are not comparable across symbols of different price levels. Normalise via slope/price.",
    "Endpoint and slope are correlated — using both as independent signals is double-counting.",
  ],

  works_well_with: ["adx", "atr", "rsi"],
  works_poorly_with: ["ema", "sma", "hma"],

  example_strategies: [
    "Linreg-Slope-Filtered Mean Reversion (daily NIFTY-50)",
    "Cross-Symbol Slope Ranking (weekly NSE F&O scan)",
  ],

  indian_context:
    "Linreg slope on weekly NIFTY-F&O stocks is a clean screening metric for the top-30 momentum baskets some retail PMS-style portfolios run. On daily NIFTY index, the 14-bar linreg slope crossing zero coincides remarkably well with major trend-regime shifts (post-budget, post-RBI policy) because the math captures the underlying directional acceleration cleanly without smoothing-window-dependent lag.",
};
