import type { StrategyExplainer } from "./_types";

export const MACD_TREND_SIGNAL: StrategyExplainer = {
  slug: "macd-trend-signal",

  what_it_does:
    "MACD measures the gap between a fast EMA (12) and a slow EMA (26), then plots a signal line (9-period EMA of that gap). When the MACD line crosses above the signal line AND both are above zero, the underlying trend is bullish AND momentum just turned up — that's the long entry. Exit on either MACD-signal cross down OR the histogram contracting for several bars (momentum exhausting).\n\nMACD's strength is that it's two signals in one indicator: trend (above/below zero) and momentum (line crossing signal). On daily charts of liquid stocks, MACD picks up regime changes a few bars after they start — slightly late but well-confirmed.",
  what_it_does_hi:
    "MACD fast EMA (12) aur slow EMA (26) ke beech gap measure karta, phir signal line plot karta (us gap ki 9-period EMA). MACD line signal line ke UPAR cross kare AND dono zero ke upar hon — underlying trend bullish AND momentum just turned up — long entry. Exit: MACD-signal cross down OR histogram several bars tak contract (momentum exhaust).\n\nMACD ki strength: ek indicator mein do signals — trend (zero ke above/below) aur momentum (line signal cross). Daily charts liquid stocks pe MACD regime changes ko few bars after start catch karta — slightly late but well-confirmed.",

  best_market_conditions:
    "Trending markets on daily timeframe of large-cap F&O stocks. Post-earnings momentum + sector-rotation breakouts. Weekly MACD for positional swing.",
  worst_market_conditions:
    "Choppy sideways markets where MACD oscillates around zero and signal-line crosses fire every few bars. Expiry-week intraday on indices.",

  common_mistakes: [
    "Trading every signal-line cross regardless of whether MACD is above or below zero — those mid-range crosses are 50/50.",
    "Using 12/26/9 settings on 5-minute intraday — that defaulting is for daily charts; on intraday it's too sluggish.",
    "Ignoring the histogram shape — a cross that fires while the histogram is already contracting is a late, weak signal.",
  ],

  realistic_returns:
    "Daily-chart edge on Indian large-caps with zero-line filter: 48-56% win rate, R:R 1:1.8 average. Monthly paper-mode at 1% risk: 2-4%. MACD on its own (no extra filter) historically underperforms with-filter; the filter matters more than the indicator. Note: most strategies have 2-3 losing months per year even when working as designed — paper-trade for at least 8 weeks before live to see your own variance, and never increase position size to 'catch up' after a losing month.",

  example_trade: {
    symbol: "HDFCBANK",
    entry: "MACD crosses above signal line, both above zero, on daily — long at ₹1,580",
    exit: "MACD crosses below signal line nine sessions later at ₹1,635",
    pnl: "+3.5% per share (₹55). Position-sized for ₹2,000 risk = ~36 shares = ₹1,980 profit",
  },

  follow_up_strategies: ["rsi-macd-confluence", "macd-histogram-momentum", "macd-divergence"],
  difficulty_score: 2,
  capital_efficiency_score: 3,
};
