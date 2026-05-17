import type { StrategyExplainer } from "./_types";

export const INSIDE_BAR_BREAKOUT: StrategyExplainer = {
  slug: "inside-bar-breakout",

  what_it_does:
    "An 'inside bar' is a candle whose entire range (high AND low) is contained within the prior candle's range. It signals compression — neither bulls nor bears could push past yesterday's extremes. The breakout rule: enter long when price closes above the inside bar's HIGH (and the prior bar's high), short when it closes below the LOW.\n\nThis is one of the cleanest 'volatility expansion after compression' setups. The inside-bar pattern objectively identifies low-volatility moments where a breakout is most informative.",
  what_it_does_hi:
    "'Inside bar' wo candle hai jiska entire range (high AND low) prior candle ke range ke andar contained ho. Ye compression signal karta — neither bulls nor bears yesterday ke extremes ke past push kar sake. Breakout rule: long enter karte jab price inside bar ke HIGH ke upar close ho (aur prior bar ke high ke upar), short jab LOW ke neeche close ho.\n\nCleanest 'volatility expansion after compression' setups mein se ek. Inside-bar pattern objectively low-volatility moments identify karta jab breakout sabse informative hota.",

  best_market_conditions:
    "Daily charts of F&O stocks consolidating before earnings/budget. Mid-week NIFTY when expiry hedging compresses range.",
  worst_market_conditions:
    "Markets that gap heavily — gap days rarely produce clean inside bars. News-driven sessions.",

  common_mistakes: [
    "Trading inside bars in isolation without trend context — in chop, both breakout directions fail equally.",
    "Stop too tight (inside the inside bar's range) — gets stopped on the very breakout test.",
    "Ignoring multi-day inside-bar sequences — a 3-bar inside-bar cluster is much more powerful than a single inside bar.",
  ],

  realistic_returns:
    "Inside-bar breakout on daily F&O with trend context (EMA-20 slope): 52-58% win rate, R:R 1:1.8. Monthly paper at 1% risk: 2-4%. Multi-bar inside clusters bump win rate to ~62%.",

  example_trade: {
    symbol: "NESTLEIND",
    entry: "Daily inside bar at ₹22,150 (range ₹22,100-22,200). Price closes ₹22,260 next day — long",
    exit: "Profit target (1.8x stop) hit at ₹22,420 six sessions later",
    pnl: "+0.7% per share (₹160). Position-sized for ₹3,000 risk = ~17 shares = ₹2,720 profit",
  },

  follow_up_strategies: ["bb-squeeze-breakout", "donchian-channel-breakout", "orb-15min"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
