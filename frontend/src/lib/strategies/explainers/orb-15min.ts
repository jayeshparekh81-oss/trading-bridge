import type { StrategyExplainer } from "./_types";

export const ORB_15MIN: StrategyExplainer = {
  slug: "orb-15min",

  what_it_does:
    "Opening Range Breakout (ORB): in the first 15 minutes after market open, the high and low form the 'opening range'. If price subsequently breaks ABOVE the range high, we go long. If it breaks BELOW, we go short. Stop on the opposite side of the range. Exit by 14:30 IST regardless (no overnight risk).\n\nThe edge: the first 15 minutes capture early institutional positioning. Breakouts of that range have a directional pull because the bigger players have already shown their hand. The cost: false breakouts ('fakeouts') are common in choppy / event-driven days.",
  what_it_does_hi:
    "Opening Range Breakout (ORB): market open ke pehle 15 minutes mein high aur low 'opening range' banate hain. Price phir range high ke UPAR break kare to long; NEECHE break to short. Stop range ke opposite side pe. Exit 14:30 IST tak (no overnight risk).\n\nEdge: pehle 15 minutes early institutional positioning capture karte. Us range ka breakout directional pull karta kyunki bade players hand already dikha chuke. Cost: choppy / event-driven days pe false breakouts ('fakeouts') common.",

  best_market_conditions:
    "Normal trading days with no major macro events. NIFTY / BANKNIFTY intraday on Mon-Wed when volatility is steady.",
  worst_market_conditions:
    "Budget day, RBI policy day, expiry-day intraday. Wide opening gaps that ALREADY broke the prior range.",

  common_mistakes: [
    "Trading the FIRST breakout aggressively — the cleanest ORB setups breakout AND retest the range edge before extending.",
    "No stop discipline — ORB trades MUST exit at 14:30 even if in profit; the edge is intraday-only.",
    "Sizing too large on the breakout itself — fakeouts cost 1× ATR; you need to survive 3-4 of them per week.",
  ],

  realistic_returns:
    "15m ORB on NIFTY F&O: 42-50% win rate (low), R:R 1:2 average. Monthly paper at 1% risk: 3-5%. The strategy generates 8-15 signals per month — good cadence for active intraday traders.",

  example_trade: {
    symbol: "NIFTY",
    entry: "9:30 IST opening range = 22,100-22,150. Price breaks 22,150 with volume — long at 22,155",
    exit: "Profit target (1.5× ATR) hit at 14:00 IST at 22,235",
    pnl: "+0.36% per unit (80 points). 1 lot (50) for ₹2,000 risk = ~₹4,000 profit",
  },

  follow_up_strategies: ["pdh-pdl-breakout", "premarket-gap", "camarilla-pivots-intraday"],
  difficulty_score: 3,
  capital_efficiency_score: 5,
};
