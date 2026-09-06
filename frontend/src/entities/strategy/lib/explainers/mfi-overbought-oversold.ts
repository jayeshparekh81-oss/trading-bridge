import type { StrategyExplainer } from "./_types";

export const MFI_OVERBOUGHT_OVERSOLD: StrategyExplainer = {
  slug: "mfi-overbought-oversold",

  what_it_does:
    "Money Flow Index (MFI) is RSI's volume-weighted cousin — it's the same 0-100 scale and same overbought/oversold zones, but the inputs are multiplied by volume. MFI < 20 means oversold WITH heavy selling volume (likely capitulation). MFI > 80 means overbought WITH heavy buying volume (likely climax).\n\nTrade rule: enter long on MFI < 20 reading followed by an MFI cross back above 20. Exit at MFI > 50. Compared to RSI, MFI filters out 'low-volume oversold' readings that often fade quickly.",
  what_it_does_hi:
    "Money Flow Index (MFI) RSI ka volume-weighted cousin — same 0-100 scale aur same overbought/oversold zones, but inputs volume se multiply hote. MFI < 20 = oversold WITH heavy selling volume (likely capitulation). MFI > 80 = overbought WITH heavy buying volume (likely climax).\n\nTrade rule: long enter karte MFI < 20 reading ke baad MFI 20 ke upar wapas cross kare. Exit MFI > 50. RSI se compare karke, MFI 'low-volume oversold' readings filter karta jo often quickly fade hote.",

  best_market_conditions:
    "Equity cash segment where volume is a meaningful signal. Mid-cap stocks where capitulation volume spikes are obvious.",
  worst_market_conditions:
    "Index F&O where 'volume' includes hedging that doesn't reflect directional conviction. Low-volume small caps.",

  common_mistakes: [
    "Treating MFI same as RSI on F&O — F&O volume reads differently due to hedging.",
    "Entering on MFI < 20 alone without the cross-back signal — extreme MFI can stay extreme for many bars.",
    "Ignoring volume-quality — MFI < 20 in a stock that trades 1 lakh shares/day is much less meaningful than in one that trades 50 lakh.",
  ],

  realistic_returns:
    "MFI < 20 reversal with cross-back-above-20 confirmation on equity cash daily: 54-60% win rate, R:R 1:1.6. Monthly paper at 1% risk: 2-4%. Slightly better than vanilla RSI-oversold on equity (the volume filter helps). Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "DLF",
    entry: "MFI = 17 (oversold with heavy volume), then crosses to 23 — long at ₹850",
    exit: "MFI = 53 nine sessions later at ₹908",
    pnl: "+6.8% per share (₹58). Position-sized for ₹2,500 risk = ~43 shares = ₹2,494 profit",
  },

  follow_up_strategies: ["rsi-oversold-bounce", "obv-divergence", "cmf-confirmation"],
  difficulty_score: 2,
  capital_efficiency_score: 4,
};
