import type { StrategyExplainer } from "./_types";

export const DONCHIAN_CHANNEL_BREAKOUT: StrategyExplainer = {
  slug: "donchian-channel-breakout",

  what_it_does:
    "The Donchian channel plots the highest high and lowest low of the past N bars. The classic 'turtle' breakout: enter long when price closes ABOVE the 20-bar Donchian high, exit when price closes below the 10-bar Donchian low. The asymmetric N (20 entry, 10 exit) reduces whipsaws while preserving trend capture.\n\nThis is the simplest mechanical trend-following setup that has been profitable in commodities and FX for decades. It works on Indian F&O too, but with materially worse win rates than mean-reversion in the typical NIFTY regime.",
  what_it_does_hi:
    "Donchian channel past N bars ka highest high aur lowest low plot karta. Classic 'turtle' breakout: long enter jab price 20-bar Donchian high ke UPAR close ho, exit jab 10-bar Donchian low ke neeche close ho. Asymmetric N (20 entry, 10 exit) whipsaws reduce karta while trend capture preserve karta.\n\nSimplest mechanical trend-following setup hai jo commodities aur FX mein decades se profitable raha. Indian F&O pe bhi kaam karta, but typical NIFTY regime mein mean-reversion se materially worse win rates ke saath.",

  best_market_conditions:
    "Commodity-correlated stocks (Tata Steel, Hindalco, ONGC) during strong commodity trends. Sector breakouts that span weeks.",
  worst_market_conditions:
    "Range-bound NIFTY years where breakouts fail at the prior swing high. Pre-budget consolidation.",

  common_mistakes: [
    "Using symmetric N (20/20) — that creates more whipsaws; the 20-entry/10-exit asymmetry is critical to the edge.",
    "Trading every breakout without volume confirmation — fake breakouts on low volume reverse fast.",
    "Sizing the same in trending and ranging years — accept that this setup has bad chop years; don't oversize.",
  ],

  realistic_returns:
    "Donchian(20/10) on daily F&O stocks: 35-45% win rate (LOW), but R:R averages 1:3 (winners are big). Monthly paper at 1% risk: 1-4% in trending years, -2 to 0% in chop. Highly regime-dependent.",

  example_trade: {
    symbol: "TATASTEEL",
    entry: "Price closes at ₹148 (20-day high was ₹146) — long",
    exit: "Price closes at ₹164 below 10-day low 22 sessions later",
    pnl: "+10.8% per share (₹16). 6 of 10 such breakouts fail; this is what the 1:3 R:R requires to be profitable.",
  },

  follow_up_strategies: ["adx-strong-trend-filter", "chandelier-exit-trail", "supertrend-rider"],
  difficulty_score: 2,
  capital_efficiency_score: 3,
};
