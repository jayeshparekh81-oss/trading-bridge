import type { StrategyExplainer } from "./_types";

export const ADX_STRONG_TREND_FILTER: StrategyExplainer = {
  slug: "adx-strong-trend-filter",

  what_it_does:
    "ADX (Average Directional Index) measures trend STRENGTH, not direction. We use it purely as a filter: only take directional setups when ADX > 25 (strong trend present). When ADX < 20, the market is ranging — block all trend-following entries.\n\nThis is not a complete strategy on its own — it's a gating filter that layers on top of any trend-following setup (EMA-cross, MACD, Supertrend). Combining a directional setup with an ADX > 25 filter typically improves win rate by 5-12 percentage points across regimes.",
  what_it_does_hi:
    "ADX (Average Directional Index) trend STRENGTH measure karta, direction nahi. Hum purely filter ki tarah use karte: directional setups only tab lo jab ADX > 25 (strong trend present). Jab ADX < 20, market ranging — sab trend-following entries block.\n\nYe akele complete strategy nahi — gating filter hai jo kisi bhi trend-following setup (EMA-cross, MACD, Supertrend) ke upar layer karta. Directional setup + ADX > 25 filter combine karke win rate typically 5-12 percentage points improve hota across regimes.",

  best_market_conditions:
    "Use it on every trend-following strategy you run. Especially impactful on EMA-crossover and MACD setups where chop is the dominant loser.",
  worst_market_conditions:
    "Pure mean-reversion strategies — they WANT low ADX. Don't apply this filter to range-trading or BB mean-reversion entries.",

  common_mistakes: [
    "Using ADX as the trade signal itself — ADX has no direction; it tells you 'strong trend exists' but not 'long or short'.",
    "Setting the threshold too low (< 20) — ADX 18-25 is the noise zone; only above 25 is reliably trending.",
    "Applying ADX filter to mean-reversion setups — they need the opposite (low ADX) to work.",
  ],

  realistic_returns:
    "ADX > 25 filter applied to EMA(9/21) crossover: lifts the bare crossover from ~45% to ~55% win rate. Monthly paper edge: +1-2 percentage points compared to unfiltered. Effect is largest in choppy market years.",

  example_trade: {
    symbol: "RELIANCE",
    entry: "EMA(9) crosses above EMA(21) at ₹2,820 — would-be entry. ADX = 28, filter PASSES, take the long",
    exit: "EMA(9) crosses below EMA(21) at ₹2,955, ADX still 26 — exit",
    pnl: "+4.8% per share (₹135). Filter prevented 3 false EMA-crossover signals earlier in the month (saved ~₹4,500 in chop)",
  },

  follow_up_strategies: ["ema-crossover-20-50", "macd-trend-signal", "supertrend-rider"],
  difficulty_score: 1,
  capital_efficiency_score: 5,
};
