import type { StrategyExplainer } from "./_types";

export const ICHIMOKU_CLOUD_CROSSOVER: StrategyExplainer = {
  slug: "ichimoku-cloud-crossover",

  what_it_does:
    "Ichimoku Kinko Hyo plots 5 lines and a 'cloud' (kumo) — a single chart that encodes trend, momentum, and S/R. The simplest tradeable rule: enter long when price closes ABOVE the cloud AND the Tenkan-sen crosses above the Kijun-sen (TK cross). Exit when price closes back inside the cloud.\n\nIchimoku's reputation for complexity is overstated — the cloud is just a forward-projected support/resistance band, and the TK cross is just a fast/slow MA cross. The combined rule filters out a lot of fake signals because price must be both trending AND above the cloud-support layer.",
  what_it_does_hi:
    "Ichimoku Kinko Hyo 5 lines aur ek 'cloud' (kumo) plot karta — ek hi chart jo trend, momentum, aur S/R encode karta. Simplest tradeable rule: long enter karte jab price cloud ke UPAR close ho AND Tenkan-sen Kijun-sen ke upar cross kare (TK cross). Exit jab price cloud ke andar wapas close ho.\n\nIchimoku ka complexity wala reputation overstated — cloud bas forward-projected support/resistance band hai, aur TK cross fast/slow MA cross hai. Combined rule lots of fake signals filter karta kyunki price ko trending AND cloud-support layer ke upar dono hona padta.",

  best_market_conditions:
    "Daily charts of trending F&O stocks. Multi-week sector breakouts where the cloud is sloping upward.",
  worst_market_conditions:
    "Sideways markets where price oscillates in and out of a flat cloud. News-driven gap days that distort projections.",

  common_mistakes: [
    "Trying to use all 5 lines — start with just price-vs-cloud and TK cross; the rest is refinement.",
    "Trading TK cross WITHOUT price-above-cloud filter — TK alone is just an MA cross with a different name.",
    "Forgetting the cloud's slope — a flat cloud means no trend regardless of TK signals.",
  ],

  realistic_returns:
    "Ichimoku price-above-cloud + TK cross on daily F&O stocks: 53-60% win rate, R:R 1:2 (good targets — the next swing high or 1.5x ATR). Monthly paper at 1% risk: 3-5%.",

  example_trade: {
    symbol: "AXISBANK",
    entry: "Price closes ₹6 above cloud, TK cross same day at ₹1,080 — long",
    exit: "Price closes back inside cloud 14 sessions later at ₹1,138",
    pnl: "+5.4% per share (₹58). Position-sized for ₹2,500 risk = ~28 shares = ₹1,625 profit",
  },

  follow_up_strategies: ["ema-crossover-9-21", "macd-trend-signal", "adx-strong-trend-filter"],
  difficulty_score: 3,
  capital_efficiency_score: 4,
};
