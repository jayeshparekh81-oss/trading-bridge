import type { StrategyExplainer } from "./_types";

export const CAMARILLA_PIVOTS_INTRADAY: StrategyExplainer = {
  slug: "camarilla-pivots-intraday",

  what_it_does:
    "Camarilla pivots compute 8 daily support/resistance levels (H1-H4, L1-L4) from prior day's H/L/C using fixed multipliers. The trade rule: on intraday charts, price tends to revert from H3/L3, and a break of H4/L4 signals trend continuation. We enter long on a pullback to L3 (or short from H3) and use the prior pivot level as stop.\n\nThis is one of the most widely-used intraday setups in Indian retail trading because it produces objective levels every morning before market open — no chart fitting needed.",
  what_it_does_hi:
    "Camarilla pivots prior day ke H/L/C se 8 daily support/resistance levels (H1-H4, L1-L4) compute karte fixed multipliers se. Trade rule: intraday charts pe price H3/L3 se revert hota tend karta, aur H4/L4 ka break trend continuation signal. L3 pe pullback pe long enter karte (ya H3 se short) aur prior pivot level stop banate.\n\nIndian retail intraday trading mein sabse widely-used setups mein se ek — har morning market open se pehle objective levels deta, koi chart fitting nahi chahiye.",

  best_market_conditions:
    "Range-bound intraday days on NIFTY/BANKNIFTY where price oscillates between H3 and L3. Stocks with predictable daily ranges (large caps, RIL, HDFC, INFY).",
  worst_market_conditions:
    "Trend days where price blows through H4/L4 in the first hour. News/event mornings. Expiry days with skewed OI flow.",

  common_mistakes: [
    "Using yesterday's wide-range day's pivots for today — if yesterday gapped, today's pivots are stretched.",
    "Trading every pivot touch — H3/L3 are highest-conviction; H1/H2/L1/L2 produce too many touches.",
    "No stop discipline — if price breaks H4 instead of reverting, exit immediately; don't average down.",
  ],

  realistic_returns:
    "Camarilla H3/L3 reversal on NIFTY F&O intraday: 55-62% win rate, R:R 1:1.2 (small intraday targets). Monthly paper at 0.5% risk per trade: 3-5%. Fires 1-2 setups per day.",

  example_trade: {
    symbol: "NIFTY",
    entry: "Open at 22,450. L3 = 22,380. Price pulls back to 22,385 at 11:00 IST with hammer — long",
    exit: "Price reaches pivot at 22,440 by 14:30 IST",
    pnl: "+0.25% per unit (55 points). 1 lot (50) for ₹1,500 risk = ~₹2,750 profit",
  },

  follow_up_strategies: ["pivot-point-bounce", "orb-15min", "vwap-bounce"],
  difficulty_score: 3,
  capital_efficiency_score: 4,
};
