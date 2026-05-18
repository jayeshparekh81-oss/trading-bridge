import type { IndicatorContent } from "./_types";

export const KAMA: IndicatorContent = {
  slug: "kama",
  name: "KAMA (Kaufman Adaptive Moving Average)",
  category: "trend",
  complexity: "advanced",

  one_liner_en:
    "Moving average that speeds up in trends and slows down in chop. Self-tuning smoothness.",
  one_liner_hi:
    "Moving average jo trends mein fast aur chop mein slow ho jaati. Self-tuning smoothness.",

  description_en:
    "KAMA was designed by Perry Kaufman to address EMA's biggest limitation: fixed smoothing across all market conditions. KAMA's smoothing constant varies bar-by-bar based on an 'Efficiency Ratio' (ER) — the absolute net price change over `period` bars divided by the sum of absolute one-bar changes. When ER is near 1.0 (price moving in a straight line), KAMA acts like a fast EMA. When ER is near 0.0 (price churning sideways), KAMA acts like a very slow EMA, ignoring the chop.\n\nThe practical benefit: KAMA crosses produce fewer false signals than EMA crosses in choppy markets, while still tracking real trends responsively. The cost: more parameters (period for ER, fast SC, slow SC) and noticeably more complex math under the hood.\n\nKAMA is well-suited to instruments that alternate between trending and sideways phases (Indian indices often, mid-cap NSE F&O stocks). On consistently trending instruments, regular EMA is simpler and works fine.",
  description_hi:
    "KAMA Perry Kaufman ne EMA ki sabse badi limitation address karne ke liye design ki — saari market conditions mein fixed smoothing. KAMA ka smoothing constant bar-by-bar vary karta hai 'Efficiency Ratio' (ER) ke base pe — `period` bars over absolute net price change divided by sum of absolute one-bar changes. ER near 1.0 (straight-line price move) hai to KAMA fast EMA jaisi behave karti hai. ER near 0.0 (price sideways churn) hai to KAMA very slow EMA jaisi, chop ignore karte hue.\n\nPractical benefit: KAMA crosses choppy markets mein EMA crosses se kam false signals produce karte, real trends responsively track karte hue. Cost: zyada parameters (ER period, fast SC, slow SC) aur noticeably zyada complex math under the hood.\n\nKAMA un instruments ke liye well-suited jo trending aur sideways phases mein alternate karte (Indian indices often, mid-cap NSE F&O stocks). Consistently trending instruments pe regular EMA simpler aur fine kaam karti hai.",

  formula_explanation:
    "ER = |close - close[period bars ago]| / sum(|close[i] - close[i-1]|) for i in window. SC = (ER × (fast_sc - slow_sc) + slow_sc)² where fast_sc = 2/(2+1) and slow_sc = 2/(30+1) for default 2/30 fast/slow EMAs. KAMA(today) = KAMA(yesterday) + SC × (close - KAMA(yesterday)). Default period: 10.",

  default_period: 10,
  period_range: [5, 50],
  common_periods: [10, 14, 20],

  use_cases: [
    {
      scenario: "Crossover signals in alternating trend/chop markets",
      what_to_do: "Use KAMA(10) crossing price (or price crossing KAMA from below) as a trend-shift trigger",
      why: "Self-tuning means fewer whipsaws when the market shifts from trending to ranging mid-session — a problem EMA crossovers handle poorly.",
    },
    {
      scenario: "Trend-strength visualisation",
      what_to_do: "KAMA's slope steepness reflects the underlying ER — a flatlining KAMA visually shows the market has lost directional momentum",
      why: "Quick visual cue without needing a separate ADX panel.",
    },
  ],

  common_signals: [
    {
      signal: "Price crosses KAMA",
      condition: "Close crosses above KAMA from below (long) or below from above (exit/short)",
      action: "Trend-shift candidate — high quality compared to EMA crosses.",
    },
    {
      signal: "KAMA flatten",
      condition: "KAMA goes from sloping to flat for multiple bars",
      action: "Trend exhausting — tighten stops, prepare to flip bias.",
    },
  ],

  pitfalls: [
    "Three parameters (ER period, fast SC, slow SC) — more knobs = more overfit risk. Stick to defaults unless backtested otherwise.",
    "Math is heavier than EMA; some charting tools have buggy KAMA implementations. Verify against a reference (TA-Lib or pandas-ta-classic).",
    "On consistently trending instruments, KAMA's adaptive behaviour offers no benefit over EMA and adds complexity.",
    "On very low-volatility stocks, ER stays near 0 and KAMA barely moves — looks broken but is correctly silent.",
  ],

  works_well_with: ["adx", "atr", "supertrend"],
  works_poorly_with: ["ema", "sma", "wma"],

  example_strategies: [
    "KAMA Price-Cross (daily NIFTY-100 stocks)",
    "KAMA Slope Trend Filter (positional F&O)",
  ],

  indian_context:
    "KAMA on daily NIFTY adapts well to the index's tendency to alternate between trending breakout phases and multi-week consolidations. For mid-cap NSE F&O stocks that have gappy intraday behaviour but cleaner daily structure, KAMA's chop-suppression makes it preferable to EMA. Less useful on weekly timeframes where the choppy/trending alternation is slower-resolution.",
};
