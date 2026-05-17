import type { StrategyExplainer } from "./_types";

export const CCI_MOMENTUM: StrategyExplainer = {
  slug: "cci-momentum",

  what_it_does:
    "CCI (Commodity Channel Index, despite the name works on all assets) measures how far the current price is from its statistical mean, expressed in units of mean absolute deviation. Two trade modes: (a) MOMENTUM — enter long when CCI crosses above +100 (strong upside momentum confirmed), exit when CCI drops below 0; (b) MEAN-REVERSION — enter long when CCI < -200 (extreme oversold), exit at 0.\n\nThis explainer focuses on the MOMENTUM use. The +100 cross filter ignores small CCI fluctuations and catches sustained directional moves.",
  what_it_does_hi:
    "CCI (Commodity Channel Index, naam ke bawajood sab assets pe kaam karta) measure karta current price apni statistical mean se kitna door hai, mean absolute deviation units mein. Do trade modes: (a) MOMENTUM — CCI +100 ke upar cross kare to long enter (strong upside momentum confirmed), 0 ke neeche aaye to exit; (b) MEAN-REVERSION — CCI < -200 (extreme oversold) to long, 0 pe exit.\n\nYe explainer MOMENTUM use pe focus karta. +100 cross filter chhote CCI fluctuations ignore karke sustained directional moves catch karta.",

  best_market_conditions:
    "Trending markets with rising ADX. Stocks breaking out of multi-day consolidations on volume.",
  worst_market_conditions:
    "Choppy markets where CCI oscillates between ±100 every 2-3 bars. Pre-earnings consolidations.",

  common_mistakes: [
    "Conflating the two modes — momentum entry says 'buy strength'; mean-reversion says 'buy weakness'. Pick one and stick with it for a given setup.",
    "Using period 14 in choppy regimes — period 20 smooths out false +100 crosses.",
    "Holding through CCI returning to 0 'in case it crosses +100 again' — when CCI drops to 0, the momentum trade is OVER.",
  ],

  realistic_returns:
    "CCI(20) momentum (+100 cross) on daily F&O stocks with ADX > 20 filter: 50-58% win rate, R:R 1:1.7. Monthly paper at 1% risk: 2-4%. Without ADX filter, returns turn neutral.",

  example_trade: {
    symbol: "ICICIBANK",
    entry: "CCI crosses above +100 at ₹1,120, ADX = 26 — long",
    exit: "CCI drops to 0 at ₹1,178 nine sessions later",
    pnl: "+5.2% per share (₹58). Position-sized for ₹2,500 risk = ~35 shares = ₹2,030 profit",
  },

  follow_up_strategies: ["rsi-macd-confluence", "adx-strong-trend-filter", "macd-trend-signal"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
