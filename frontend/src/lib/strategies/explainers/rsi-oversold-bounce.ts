import type { StrategyExplainer } from "./_types";

export const RSI_OVERSOLD_BOUNCE: StrategyExplainer = {
  slug: "rsi-oversold-bounce",

  what_it_does:
    "RSI(14) measures how much of recent price action has been up-moves vs down-moves on a 0-100 scale. Below 30 = 'oversold' (lots of selling, possibly exhausting). We wait for RSI to cross BACK above 30 from below — that's the moment selling pressure broke and bulls are stepping in. Exit when RSI hits 70 (overbought) or crosses below 50 (momentum failed).\n\nThis is the textbook beginner mean-reversion setup. It works because in range-bound markets, oscillators do mean-revert. It fails in strong trends — RSI can stay below 30 for many bars during a real downtrend and 'oversold' never resolves into a bounce.",
  what_it_does_hi:
    "RSI(14) measure karta recent price action ka kitna up-moves vs down-moves 0-100 scale pe. 30 ke neeche = 'oversold' (lots of selling, possibly exhausting). RSI 30 ke neeche se WAPAS upar cross kare wala moment dhundhte — selling pressure broke aur bulls step in kar rahe. RSI 70 (overbought) hit kare ya 50 ke neeche cross kare (momentum fail) to exit.\n\nYeh textbook beginner mean-reversion setup hai. Range-bound markets mein kaam karta kyunki oscillators mean-revert karte. Strong trends mein fail karta — real downtrend mein RSI kaafi bars 30 ke neeche reh sakti aur 'oversold' kabhi bounce mein resolve nahi hota.",

  best_market_conditions:
    "Sideways / range-bound NIFTY weeks. Daily charts of stable large-caps. Pre-event consolidations where the market is waiting for news.",
  worst_market_conditions:
    "Strong directional trends (RSI stays below 30 the whole way down). Earnings-week volatility. Gap days where RSI gaps from 50 to 25 with no actual oversold dynamic.",

  common_mistakes: [
    "Buying every 30-cross without a trend filter — in downtrends this is a slow-bleed strategy.",
    "Setting stop too tight (≤ 0.5%) — normal bounces shake out before recovery completes.",
    "Holding past 70 hoping for more — overbought reversals from a 30-bounce are usually the right exit.",
  ],

  realistic_returns:
    "Range-filtered (ADX < 20) RSI bounce on Indian large-caps: 55-62% win rate, R:R 1:1.5. Monthly paper return at 1% risk: 2-4%. Without the range filter, returns collapse to 0-1% in trending months.",

  example_trade: {
    symbol: "NIFTY",
    entry: "RSI(14) crosses above 30 from below, ADX < 18 (range regime) — long at 22,150",
    exit: "RSI crosses above 70 four sessions later at 22,420",
    pnl: "+1.2% per unit (270 points). 1 lot (50) for ₹1,500 risk = ~₹13,500 profit",
  },

  follow_up_strategies: ["rsi-divergence", "rsi-macd-confluence", "bb-rsi-oversold"],
  difficulty_score: 1,
  capital_efficiency_score: 3,
};
