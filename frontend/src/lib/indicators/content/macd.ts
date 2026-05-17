import type { IndicatorContent } from "./_types";

export const MACD: IndicatorContent = {
  slug: "macd",
  name: "MACD (Moving Average Convergence Divergence)",
  category: "momentum",
  complexity: "beginner",

  one_liner_en:
    "Difference between a fast and slow EMA, plus a signal line. Crosses signal momentum shifts.",
  one_liner_hi:
    "Fast aur slow EMA ka difference, plus ek signal line. Crosses momentum shifts batate hain.",

  description_en:
    "MACD plots three things: the MACD line (fast EMA minus slow EMA, default 12 minus 26), a signal line (EMA of the MACD line, default 9 periods), and a histogram (MACD minus signal). The MACD line tells you how stretched a faster average is from a slower one; the signal line is a smoothed lag of that stretch; the histogram shows the gap between them, which expands when momentum accelerates and shrinks when momentum cools.\n\nMost traders use one of three setups. The signal-line cross: MACD crosses above its signal line for a long, below for a short. The zero-line cross: MACD crosses above zero for trend confirmation up, below for trend down. Divergence: same idea as RSI — price prints a new extreme but MACD doesn't, hinting at exhaustion.\n\nMACD is a trend-momentum hybrid. It doesn't bound itself like RSI (no 0-100 cap), which means very strong moves can push MACD to large absolute values and then the signal-line cross fires very late. On choppy days the histogram flips rapidly back and forth — that's not a trade signal, that's noise.\n\nThe default 12-26-9 setting was picked by Gerald Appel for 1970s daily charts. It is not sacred. Faster settings (5-13-1, 8-17-9) suit intraday; slower (19-39-9) suit weekly positional.",
  description_hi:
    "MACD teen cheezein plot karta hai: MACD line (fast EMA minus slow EMA, default 12 minus 26), signal line (MACD line ki EMA, default 9 periods), aur histogram (MACD minus signal). MACD line batati hai faster average slower average se kitni stretched hai; signal line uska smoothed lag hai; histogram dono ke beech ka gap dikhata hai — momentum accelerate hone pe expand, cool hone pe shrink.\n\nTraders mostly teen setups use karte hain. Signal-line cross: MACD apni signal line ke upar cross kare long ke liye, neeche cross kare short ke liye. Zero-line cross: MACD zero ke upar cross kare trend up confirmation, neeche cross kare trend down. Divergence: same idea as RSI — price naya extreme banaye but MACD nahi, exhaustion hint karta hai.\n\nMACD trend-momentum hybrid hai. RSI ki tarah bounded nahi hai (no 0-100 cap), matlab very strong moves MACD ko large absolute values tak push kar sakte hain aur signal-line cross bahut late fire hota hai. Choppy days mein histogram rapidly flip karta hai — woh trade signal nahi, noise hai.\n\nDefault 12-26-9 setting Gerald Appel ne 1970s daily charts ke liye choose ki thi. Sacred nahi hai. Faster settings (5-13-1, 8-17-9) intraday ke liye; slower (19-39-9) weekly positional ke liye.",

  formula_explanation:
    "MACD line = EMA(close, fast) - EMA(close, slow). Signal line = EMA(MACD line, signal). Histogram = MACD - Signal. Industry default: fast=12, slow=26, signal=9. The MACD line is a difference of EMAs, so it has no fixed bounds — its magnitude scales with price.",

  default_period: 12,
  period_range: [3, 50],
  common_periods: [12, 26, 9],

  use_cases: [
    {
      scenario: "Trend confirmation on entry",
      what_to_do: "Require MACD > 0 AND MACD > signal before going long",
      why: "Filters out counter-trend longs in obvious downtrends — the dual condition is harder to satisfy in chop than either alone.",
    },
    {
      scenario: "Exit on momentum exhaustion",
      what_to_do: "Exit longs when the MACD histogram contracts for 3+ consecutive bars while price still ticks up",
      why: "Histogram shrink with rising price is the textbook bearish divergence — you're getting paid less per bar even though tape looks fine.",
    },
    {
      scenario: "BANKNIFTY intraday momentum",
      what_to_do: "Use 5-13-1 setting on 5-min candles for faster cross signals",
      why: "BANKNIFTY's 5-min moves are fast; the default 12-26-9 cross comes 30-45 minutes too late on intraday breakouts.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish signal-line cross",
      condition: "MACD crosses above its signal line",
      action: "Long entry candidate — stronger if zero-line is already crossed up.",
    },
    {
      signal: "Bearish signal-line cross",
      condition: "MACD crosses below its signal line",
      action: "Long exit / short entry candidate.",
    },
    {
      signal: "Zero-line cross up",
      condition: "MACD crosses above 0",
      action: "Trend regime change to bullish — used as a bias filter, not a trigger.",
    },
    {
      signal: "Histogram divergence",
      condition: "Price new high, histogram lower high (or price new low, histogram higher low)",
      action: "Tighten stops or scale out — momentum is waning.",
    },
  ],

  pitfalls: [
    "MACD is not bounded — large gaps can produce huge MACD values and the system 'looks' overbought when it's actually just a price-scale artifact. Always read MACD relative to its own recent range, not absolute numbers.",
    "Signal-line crosses are LAGGING — by definition the cross fires after the move has started. Use it for confirmation, not prediction.",
    "12-26-9 is not gospel. On 5-min intraday, that setting is sluggish; on weekly, it's twitchy.",
    "Two MACD setups on the same chart (one fast, one slow) often disagree — that's the indicator working, not malfunctioning.",
    "Cross signals during news / event spikes are unreliable — MACD doesn't model volatility regime.",
  ],

  works_well_with: ["ema", "supertrend", "vwap", "volume-profile"],
  works_poorly_with: ["rsi", "stochastic"],

  example_strategies: [
    "MACD Histogram Reversal (15m NIFTY)",
    "MACD + Supertrend Pullback (1h FINNIFTY)",
    "MACD Divergence Hunter (daily NSE-500 stocks)",
  ],

  indian_context:
    "On NIFTY weekly expiries, MACD signal-line crosses are reliable into Tuesday-Wednesday but become noisy on Thursday morning as gamma squeeze and OI unwinding distort minute-level momentum. For sector indices (NIFTY IT, NIFTY PSU BANK), MACD on the daily filters cleaner trend regimes than on individual stocks because sector aggregation smooths idiosyncratic noise. BANKNIFTY's higher beta makes MACD histograms larger in absolute value — don't compare BANKNIFTY MACD numbers to NIFTY MACD numbers directly.",
};
