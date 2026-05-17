import type { StrategyExplainer } from "./_types";

export const RANGE_TRADING_SR: StrategyExplainer = {
  slug: "range-trading-sr",

  what_it_does:
    "When an instrument is clearly range-bound (price oscillating between identifiable support and resistance levels for 10+ sessions, ADX < 20), trade the levels: buy at support with a stop just below, sell at resistance with a stop just above. Targets are the OTHER side of the range.\n\nThis is the most basic mean-reversion playbook and works mechanically when the range is real. The skill is in (a) correctly identifying that you're in a range (not the start of a trend) and (b) exiting fast when a range BREAKS.",
  what_it_does_hi:
    "Jab koi instrument clearly range-bound ho (price 10+ sessions ke liye identifiable support aur resistance levels ke beech oscillate karta, ADX < 20), levels ko trade karo: support pe buy thoda neeche stop ke saath, resistance pe sell thoda upar stop ke saath. Targets range ki DOOSRI side.\n\nMost basic mean-reversion playbook hai aur range real ho to mechanically kaam karta. Skill hai (a) correctly identify karna ki range mein ho (trend ki start nahi) aur (b) range BREAK ho to fast exit karna.",

  best_market_conditions:
    "Pre-event NIFTY consolidations (pre-budget, pre-RBI policy). Low-VIX environments where ranges hold for weeks.",
  worst_market_conditions:
    "Trending markets where 'range' is actually a pause. Post-event sessions where ranges break violently.",

  common_mistakes: [
    "Calling a pullback a range — you need 3+ touches of each level over 10+ sessions to call it a range.",
    "Holding through a range break — when support breaks on volume, exit IMMEDIATELY; don't average down.",
    "Setting profit targets short of the opposite end — the whole point is mean reversion to the OTHER level.",
  ],

  realistic_returns:
    "Range-trading on NIFTY in confirmed low-ADX regimes: 60-67% win rate, R:R 1:2 (the range width is your target). Monthly paper at 1% risk: 3-6% in confirmed range months, -1 to 0% in misidentified 'ranges' that were trends.",

  example_trade: {
    symbol: "NIFTY",
    entry: "Confirmed range 22,200-22,600 for 12 sessions. Price pulls to 22,210 with bullish hammer — long",
    exit: "Price reaches range top 22,580 nine sessions later",
    pnl: "+1.7% per unit (370 points). 1 lot (50) for ₹2,000 risk = ~₹9,250 profit",
  },

  follow_up_strategies: ["bb-mean-reversion", "keltner-channel-bounce", "pivot-point-bounce"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
