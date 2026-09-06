import type { StrategyExplainer } from "./_types";

export const PREMARKET_GAP: StrategyExplainer = {
  slug: "premarket-gap",

  what_it_does:
    "When NIFTY or a major stock opens with a meaningful gap (> 0.5% from prior close), the gap is usually news-driven. Statistically, the FIRST 15 minutes of trading either: (a) extends the gap (gap-and-go) — strong continuation; or (b) fills the gap — fading the news. We measure the 5-min trend in the first 15 minutes, then enter in that direction with a stop on the opposite side of the gap.\n\nThe edge: gap days have above-average directional persistence on average. The cost: false setups happen on gap-fill days, where the early move reverses.",
  what_it_does_hi:
    "NIFTY ya major stock meaningful gap se open ho (prior close se > 0.5%) to gap usually news-driven. Statistically, trading ke pehle 15 minutes: (a) gap extend karte (gap-and-go) — strong continuation; ya (b) gap fill karte — news fade. Pehle 15 minutes mein 5-min trend measure karte, phir us direction mein enter karte gap ke opposite side pe stop ke saath.\n\nEdge: gap days pe above-average directional persistence average mein. Cost: gap-fill days pe false setups jab early move reverse hota.",

  best_market_conditions:
    "Macro-news mornings (post-FOMC, post-earnings of NIFTY heavyweights). Gap > 0.5% but < 2% (smaller gaps lack directional conviction; bigger gaps usually retrace).",
  worst_market_conditions:
    "Tiny gaps (< 0.3%) where the 'gap' is noise. Holiday-shortened weeks. Expiry-day morning gaps that get whipsawed by OI flow.",

  common_mistakes: [
    "Entering immediately at open — wait for the first 15 minutes to establish direction. Pre-15-min entries are pure guessing.",
    "Ignoring gap SIZE — small gaps fill more often; very large gaps retrace.",
    "No stop discipline — gap trades can rip both directions early; the stop is the entire trade thesis.",
  ],

  realistic_returns:
    "Premarket-gap on NIFTY F&O with 0.5-2% gap filter: 48-55% win rate, R:R 1:1.8. Monthly paper at 1% risk: 2-4% — fires only on gap days (8-12 setups per month). Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "NIFTY",
    entry: "Gap up 0.8% from prior close. First 15 min trends up. Long at 22,310",
    exit: "Profit target (gap-and-go magnitude = 2× gap size) hit at 12:00 IST at 22,485",
    pnl: "+0.79% per unit (175 points). 1 lot (50) for ₹2,000 risk = ~₹8,750 profit",
  },

  follow_up_strategies: ["orb-15min", "pdh-pdl-breakout", "volume-spike-price-confirm"],
  difficulty_score: 3,
  capital_efficiency_score: 4,
};
