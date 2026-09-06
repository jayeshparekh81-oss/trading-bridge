import type { StrategyExplainer } from "./_types";

export const SQUEEZE_MOMENTUM: StrategyExplainer = {
  slug: "squeeze-momentum",

  what_it_does:
    "The 'squeeze' setup (popularised by John Carter) fires when Bollinger Bands contract INSIDE Keltner Channels — volatility has compressed to the point where a directional explosion is likely. We wait for the squeeze to RELEASE (BB expand back outside Keltner), then enter in the direction of the momentum histogram at release.\n\nThe setup is mechanical and fires infrequently (1-3 times per month per F&O stock), which is the point — only the highest-quality compression-to-expansion moments get traded.",
  what_it_does_hi:
    "'Squeeze' setup (John Carter ne popularise kiya) tab fire hota jab Bollinger Bands Keltner Channels ke ANDAR contract ho jaayein — volatility itni compressed ki directional explosion likely. Squeeze RELEASE hone ka wait karte (BB Keltner ke bahar wapas expand), phir release pe momentum histogram ki direction mein enter karte.\n\nSetup mechanical hai aur infrequently fire karta (per F&O stock per month 1-3 times) — wahi point hai: sirf highest-quality compression-to-expansion moments trade hote.",

  best_market_conditions:
    "Pre-event consolidations (pre-earnings, pre-policy). Stocks coming out of multi-week ranges.",
  worst_market_conditions:
    "Already-volatile markets where BB never compress inside Keltner. News-driven gap days that release squeezes overnight (you miss the move).",

  common_mistakes: [
    "Entering DURING the squeeze, not after release — squeezes can persist for weeks; the release IS the signal.",
    "Ignoring the momentum histogram direction at release — squeeze release WITHOUT momentum is a coin flip.",
    "Holding for too long — squeeze trades have a quick first move; exit when momentum histogram fades.",
  ],

  realistic_returns:
    "BB-inside-Keltner squeeze release with momentum confirmation on daily F&O: 55-62% win rate, R:R 1:2 (good targets). Monthly paper at 1% risk: 2-4% — fires infrequently but high quality. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "BHARTIARTL",
    entry: "BB inside Keltner for 11 sessions. Squeeze releases with positive momentum at ₹1,210 — long",
    exit: "Momentum histogram fades to zero at ₹1,275 seven sessions later",
    pnl: "+5.4% per share (₹65). Position-sized for ₹2,500 risk = ~38 shares = ₹2,470 profit",
  },

  follow_up_strategies: ["bb-squeeze-breakout", "inside-bar-breakout", "donchian-channel-breakout"],
  difficulty_score: 3,
  capital_efficiency_score: 5,
};
