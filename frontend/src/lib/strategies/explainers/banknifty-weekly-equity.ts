import type { StrategyExplainer } from "./_types";

export const BANKNIFTY_WEEKLY_EQUITY: StrategyExplainer = {
  slug: "banknifty-weekly-equity",

  what_it_does:
    "A BANKNIFTY-focused weekly trade tracking the higher-beta index's directional bias coming out of each new weekly expiry. After Wednesday's options expiry settles, fresh positioning starts on Thursday morning. We use a multi-indicator confluence (price > 20-EMA, RSI > 50, ADX > 20) to set bias for the next 5 sessions and enter on a confirmed pullback.\n\nWhy BANKNIFTY specifically: it's the highest-beta major Indian index, with daily moves often 2x NIFTY in absolute %. That makes weekly directional trades both higher-reward AND higher-risk per ATR.",
  what_it_does_hi:
    "BANKNIFTY-focused weekly trade jo higher-beta index ke directional bias ko har naya weekly expiry ke baad track karta. Wednesday ke options expiry settle hone ke baad, fresh positioning Thursday subah start hota. Multi-indicator confluence (price > 20-EMA, RSI > 50, ADX > 20) use karke next 5 sessions ka bias set karte aur confirmed pullback pe enter karte.\n\nBANKNIFTY specifically kyun: highest-beta major Indian index, daily moves often NIFTY ke 2x absolute % mein. Weekly directional trades higher-reward AND higher-risk per ATR.",

  best_market_conditions:
    "Post-expiry weeks (Thursday-Wednesday) with clear macro bias. Earnings season for top BANKNIFTY constituents (HDFC, ICICI, SBI, Kotak).",
  worst_market_conditions:
    "RBI policy weeks (rate decisions whipsaw banks). Inflation-print weeks. Wide-gap-open Thursdays where the bias is already in price.",

  common_mistakes: [
    "Sizing the same as a NIFTY trade — BANKNIFTY's higher ATR means same lot = 2x risk.",
    "Holding through Wednesday afternoon — expiry-day positioning unwinds; close by Wednesday morning.",
    "Trading on weeks where the multi-indicator confluence isn't unanimous — partial confluence is the same as none.",
  ],

  realistic_returns:
    "BANKNIFTY weekly with strict confluence filter: 50-58% win rate, R:R 1:2 average. Monthly paper at 1% risk: 4-7% — higher than NIFTY-equivalent setups due to BANKNIFTY beta. Variance high.",

  example_trade: {
    symbol: "BANKNIFTY",
    entry: "Thursday open. Price > 20-EMA, RSI = 56, ADX = 24. Pullback to 47,300 with hammer — long",
    exit: "Wednesday morning at 48,200 (next expiry settlement approaching)",
    pnl: "+1.9% per unit (900 points). 1 lot (15) for ₹3,000 risk = ~₹13,500 profit",
  },

  follow_up_strategies: ["adx-strong-trend-filter", "supertrend-rider", "rsi-macd-confluence"],
  difficulty_score: 3,
  capital_efficiency_score: 4,
};
