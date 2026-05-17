import type { StrategyExplainer } from "./_types";

export const PDH_PDL_BREAKOUT: StrategyExplainer = {
  slug: "pdh-pdl-breakout",

  what_it_does:
    "PDH = Previous Day's High; PDL = Previous Day's Low. These are universally-watched intraday reference levels — every trader's chart has these horizontal lines drawn. A clean break above PDH (with volume) is interpreted as 'today is going to trend up'; below PDL = downtrend day. Stop on the opposite side of the level; intraday-only exit by 15:00 IST.\n\nThe edge: PDH/PDL are reference levels institutions defend or attack. Breaking them with conviction is a signal that yesterday's bias has flipped. The cost: tight stops mean many small losses when the breakout fails (which it does, often, on choppy days).",
  what_it_does_hi:
    "PDH = Previous Day's High; PDL = Previous Day's Low. Universally-watched intraday reference levels — har trader ke chart pe yeh horizontal lines hote. PDH ke upar clean break (volume ke saath) = 'today is going to trend up'; PDL ke neeche = downtrend day. Stop level ke opposite side; intraday-only exit 15:00 IST tak.\n\nEdge: PDH/PDL reference levels jo institutions defend ya attack karte. Conviction se break karna signal hai ki kal ka bias flip ho gaya. Cost: tight stops matlab choppy days pe many small losses jab breakout fail kare.",

  best_market_conditions:
    "Trending days on NIFTY/BANKNIFTY where ADX is rising. Post-overnight-news days (US close, earnings).",
  worst_market_conditions:
    "Range days where PDH/PDL are inside the previous day's chop. Holiday-shortened weeks with thin volume.",

  common_mistakes: [
    "Front-running the breakout (entering before price actually closes beyond) — that's how fakeouts catch you.",
    "Not requiring volume confirmation — a breakout on light volume usually retraces.",
    "Holding through the day's reversal — the strategy is intraday; the edge dies after 15:00 IST.",
  ],

  realistic_returns:
    "PDH/PDL on NIFTY intraday with volume filter: 45-52% win rate, R:R 1:1.5. Monthly paper at 1% risk: 2-5%. Best in trending months — sideways months can deliver flat to slightly negative results.",

  example_trade: {
    symbol: "BANKNIFTY",
    entry: "PDH = 47,500. Price closes 47,520 on 5-min bar with 2× avg volume — long at 47,520",
    exit: "Profit target (PDH + 1 ATR) hit at 13:30 IST at 47,720",
    pnl: "+0.42% per unit (200 points). 1 lot (15) for ₹2,500 risk = ~₹3,000 profit",
  },

  follow_up_strategies: ["orb-15min", "premarket-gap", "camarilla-pivots-intraday"],
  difficulty_score: 3,
  capital_efficiency_score: 4,
};
