import type { StrategyExplainer } from "./_types";

export const VOLUME_SPIKE_PRICE_CONFIRM: StrategyExplainer = {
  slug: "volume-spike-price-confirm",

  what_it_does:
    "Volume tells you HOW MANY people care; price tells you which way they're voting. A volume spike (bar volume > 2x 20-bar average) WITH a strong directional candle = high-conviction move. Entry: long on the close of a green volume-spike candle that breaks above the prior bar's high. Stop: below the spike candle's low.\n\nVolume confirmation filters out 'thin tape' moves that look directional but reverse on the next bar because nobody actually committed. The 2x-average threshold is the conservative cut-off; some traders use 1.5x.",
  what_it_does_hi:
    "Volume batata HOW MANY people care; price batata kis side vote kar rahe. Volume spike (bar volume > 2x 20-bar average) WITH strong directional candle = high-conviction move. Entry: green volume-spike candle ke close pe long jo prior bar ke high ke upar break kare. Stop: spike candle ke low ke neeche.\n\nVolume confirmation 'thin tape' moves filter karta jo directional dikhte but next bar pe reverse hote kyunki actually koi committed nahi tha. 2x-average threshold conservative cut-off; some traders 1.5x use karte.",

  best_market_conditions:
    "Stock breakouts on volume — gap-and-go mornings, sector-rotation days. Cash equity (volume reads cleaner than F&O).",
  worst_market_conditions:
    "Expiry-day F&O where hedging inflates volume. Pre-event sessions where volume spikes are positioning, not direction.",

  common_mistakes: [
    "Counting 'volume spike' on a candle with a long shadow — the directional close matters as much as the volume itself.",
    "Chasing the volume spike after it's already extended — entry should be on the spike bar's close or the next bar's break.",
    "Ignoring relative volume context — a 'spike' on a holiday-shortened day might just be normal volume.",
  ],

  realistic_returns:
    "Volume-spike (>2x) with directional close on cash equity daily: 54-61% win rate, R:R 1:1.6. Monthly paper at 1% risk: 3-5%. Most effective as a CONFIRMATION layer on other setups (e.g., volume-confirmed breakout) — standalone volume-spike entries are weaker. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "VEDL",
    entry: "Volume spikes to 2.4x avg with green candle closing at ₹485 above prior high ₹478 — long",
    exit: "Profit target 1.6x risk hit at ₹510 six sessions later",
    pnl: "+5.2% per share (₹25). Position-sized for ₹2,000 risk = ~80 shares = ₹2,000 profit",
  },

  follow_up_strategies: ["bb-squeeze-breakout", "premarket-gap", "obv-divergence"],
  difficulty_score: 1,
  capital_efficiency_score: 4,
};
