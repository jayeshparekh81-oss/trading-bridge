import type { IndicatorContent } from "./_types";

export const GAUSSIAN_CHANNEL: IndicatorContent = {
  slug: "gaussian-channel",
  name: "Gaussian Channel",
  category: "advanced",
  complexity: "advanced",

  one_liner_en:
    "Pole-filter-smoothed moving average with True-Range bands. Cleaner trend signals than EMA/Bollinger pairs, popular for low-frequency strategies.",
  one_liner_hi:
    "Pole-filter-smoothed moving average True-Range bands ke saath. EMA/Bollinger pairs se cleaner trend signals, low-frequency strategies mein popular hai.",

  description_en:
    "Gaussian Channel is a band-style indicator built around a Gaussian filter (a smoother math version of an EMA, using a multi-pole infinite-impulse-response filter that approximates a normal-distribution-shaped weighting). The middle line is a Gaussian filter of the source price; the bands are placed at ATR-distance above and below.\n\nThe practical difference vs Bollinger / Keltner: Gaussian smoothing has much lower phase lag than EMA at equivalent noise rejection. This means the middle line tracks trends more accurately without the choppiness of a fast EMA or the lag of a slow one. The 'price closing above the upper band' signal therefore fires earlier in real trends and less often in chop.\n\nKey parameters: `poles` (typically 4, controls how aggressive the smoothing is), `period` (typically 144 — yes, large), and an ATR multiplier (typically 1.414 = sqrt(2)). The big period is unusual and is what gives Gaussian Channel its slow-trend character — designed for daily charts and weekly setups, not intraday scalping.\n\nGaussian Channel got popular in the 2020s among crypto and equity quant retail looking for low-frequency 'buy and hold during green, sit out during red' regime systems.",
  description_hi:
    "Gaussian Channel ek band-style indicator hai jo Gaussian filter ke around bana hai (EMA ka smoother math version, multi-pole infinite-impulse-response filter use karta jo normal-distribution-shaped weighting approximate karta hai). Middle line source price ka Gaussian filter hai; bands ATR-distance pe upar aur neeche.\n\nBollinger / Keltner vs practical difference: Gaussian smoothing ki equivalent noise rejection pe phase lag bahut kam hai EMA se. Matlab middle line trends ko zyada accurately track karti hai bina fast EMA ki choppiness ya slow EMA ke lag ke. 'Price upper band ke upar close' signal real trends mein earlier fire hota aur chop mein kam.\n\nKey parameters: `poles` (typically 4, smoothing ki aggressiveness control), `period` (typically 144 — haan, bada), aur ATR multiplier (typically 1.414 = sqrt(2)). Bada period unusual hai aur isi se Gaussian Channel ka slow-trend character aata — daily charts aur weekly setups ke liye designed, intraday scalping nahi.\n\nGaussian Channel 2020s mein crypto aur equity quant retail ke beech popular hua jo low-frequency 'green mein buy-and-hold, red mein sit-out' regime systems dhundhte the.",

  formula_explanation:
    "Source = HLC3 by default = (high + low + close) / 3. Apply N-pole Gaussian filter to source: F(x) = (1-α)^N × x + N × (1-α)^(N-1) × α × F_prev + … (the recursive multi-pole IIR). α = (cos(2π / period) + sin(2π / period) - 1) / cos(2π / period). Middle = Gaussian_filtered(source). Upper = Middle + ATR(period) × mult. Lower = Middle - ATR(period) × mult. Defaults: poles=4, period=144, mult=1.414.",

  default_period: 144,
  period_range: [20, 500],
  common_periods: [50, 144, 200],

  use_cases: [
    {
      scenario: "Long-only regime trading on daily charts",
      what_to_do: "Long when price closes above the upper band AND middle line is sloping up; exit when price closes below the middle line",
      why: "Captures multi-week trends with minimal whipsaws. Sit-out periods preserve capital and avoid choppy losses.",
    },
    {
      scenario: "Weekly trend filter for swing trades",
      what_to_do: "Use weekly Gaussian Channel direction (middle line slope) as a bias filter for daily setups",
      why: "Higher-timeframe trend filter combined with lower-timeframe entry signals — classic top-down combination, but with cleaner trend definition.",
    },
    {
      scenario: "Long-only buy-and-hold gating",
      what_to_do: "Hold index ETF (or NIFTYBEES) only when daily Gaussian Channel is green (price > middle, middle up-sloping)",
      why: "Simple regime-aware passive strategy that historically misses most major drawdowns at the cost of giving up some upside.",
    },
  ],

  common_signals: [
    {
      signal: "Bullish trend regime",
      condition: "Middle line slopes up AND price closes above the middle line",
      action: "Long-bias regime — enable trend-following strategies.",
    },
    {
      signal: "Trend regime change",
      condition: "Middle line slope flips from down to up (or vice versa)",
      action: "Regime-trade entry / exit. Rare but high-conviction.",
    },
    {
      signal: "Upper band break",
      condition: "Price closes above the upper band after period inside",
      action: "Strong-trend confirmation; continuation entry.",
    },
  ],

  pitfalls: [
    "144-period default is large. On a daily chart that's 7+ months — Gaussian Channel produces VERY few signals per year. Not for active traders.",
    "The math is complex compared to SMA / EMA. Bugs in third-party implementations are common. Use a trusted library or verify against a reference.",
    "Doesn't work for intraday or short-term setups — the smoothing is too slow. Don't try to 'speed it up' with smaller periods; that defeats the design.",
    "Gaussian filtering introduces some lag (less than EMA, but not zero). Trend reversals are confirmed late.",
    "Different pole counts produce visibly different lines on the same chart. Be specific about your pole setting.",
  ],

  works_well_with: ["adx", "atr", "supertrend"],
  works_poorly_with: ["stochastic", "rsi", "williams-r"],

  example_strategies: [
    "Daily Gaussian Channel Long-Only Regime (NIFTY positional)",
    "Weekly Gaussian Trend Filter for Daily Setups",
    "Crypto-inspired BTC-style long-and-flat with Indian indices",
  ],

  indian_context:
    "Gaussian Channel adoption in Indian retail is still small but growing — typically discussed in quant-leaning Telegram communities and YouTube channels focusing on long-only regime systems on NIFTY and NIFTYBEES. The slow signal cadence suits SIP-style traders who want to avoid drawdown regimes without the complexity of full timing systems. For BANKNIFTY's higher volatility, some practitioners reduce the period to 100 and the multiplier to 1.2 — the standard 144 / 1.414 is too slow for the index's faster regime shifts. The indicator is in use on a live TRADETRI strategy as of 2026, making it a high-priority entry in this catalog.",
};
