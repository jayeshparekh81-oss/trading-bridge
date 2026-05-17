import type { StrategyExplainer } from "./_types";

export const PIVOT_POINT_BOUNCE: StrategyExplainer = {
  slug: "pivot-point-bounce",

  what_it_does:
    "Classical floor-trader pivots compute a daily Pivot Point (P) and three supports (S1, S2, S3) and three resistances (R1, R2, R3) from prior day's H/L/C. The trade rule: on intraday charts, price tends to bounce off these levels. Buy a reversal candle at S1 or S2; exit at P or R1.\n\nThe edge is modest but real because so many Indian intraday traders watch these levels — they're partially self-fulfilling. Best treated as a 'roadmap' rather than a standalone signal.",
  what_it_does_hi:
    "Classical floor-trader pivots prior day ke H/L/C se daily Pivot Point (P) aur teen supports (S1, S2, S3) aur teen resistances (R1, R2, R3) compute karte. Trade rule: intraday charts pe price in levels se bounce hota tend karta. Reversal candle pe S1 ya S2 pe buy; P ya R1 pe exit.\n\nEdge modest but real kyunki itne saare Indian intraday traders in levels ko watch karte — partially self-fulfilling hain. 'Roadmap' ki tarah treat karna best, standalone signal ki tarah nahi.",

  best_market_conditions:
    "Range-bound intraday sessions on NIFTY/BANKNIFTY/large caps. Days following a wide-range previous day.",
  worst_market_conditions:
    "Trending intraday days where price slices through pivot levels without pause. Gap-heavy mornings where levels are pre-printed.",

  common_mistakes: [
    "Trading every pivot level — P/S1/R1 are highest-touch; S2/R2 are lower-conviction; S3/R3 are usually too far.",
    "Entering at the level without a reversal candle — pivot levels are 'where to look', not 'when to act'.",
    "No stop discipline — pivot trades that fail need to be cut fast (within 2 candles).",
  ],

  realistic_returns:
    "Pivot S1/R1 bounce with reversal-candle confirmation on NIFTY intraday: 54-60% win rate, R:R 1:1.3 (small intraday targets). Monthly paper at 0.5% risk per trade: 2-4%.",

  example_trade: {
    symbol: "NIFTY",
    entry: "Open 22,450. S1 = 22,395. Price pulls to 22,398 with bullish hammer — long at 22,405",
    exit: "Price reaches Pivot at 22,440 by 13:30 IST",
    pnl: "+0.16% per unit (35 points). 1 lot (50) for ₹1,500 risk = ~₹1,750 profit",
  },

  follow_up_strategies: ["camarilla-pivots-intraday", "vwap-bounce", "orb-15min"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
