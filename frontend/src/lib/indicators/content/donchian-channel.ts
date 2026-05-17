import type { IndicatorContent } from "./_types";

export const DONCHIAN_CHANNEL: IndicatorContent = {
  slug: "donchian-channel",
  name: "Donchian Channel",
  category: "volatility",
  complexity: "beginner",

  one_liner_en:
    "The highest high and lowest low of the last N bars. New 20-day high / low signals are the original 'Turtle' breakout rule.",
  one_liner_hi:
    "Last N bars ka highest high aur lowest low. Naya 20-day high / low signal hi original 'Turtle' breakout rule hai.",

  description_en:
    "Donchian Channel plots three lines: the upper band is the highest high over `period` bars, the lower band is the lowest low, and the middle is their average. There's no smoothing — when a new high prints, the upper band steps up instantly; same for the lower band on new lows.\n\nMade famous by Richard Dennis's 1980s Turtle Traders system: enter long on a 20-day high breakout, exit on a 10-day low. That single rule, applied across futures, generated legendary returns. The reason it works: in trending markets, the highest-high keeps rising, so each new bar is a fresh entry signal; in chop, breakouts fail quickly but the loss is bounded by the channel width.\n\nDonchian is the OG breakout indicator. Compared to Bollinger and Keltner:\n• Donchian: hard rectangle bounded by actual extremes (no math).\n• Bollinger: soft curve based on standard deviation.\n• Keltner: soft curve based on ATR.\n\nDonchian's hardness makes it visually intuitive and easy to backtest, but it ignores the 'how' of the move — a 20-day high reached on a single explosive bar reads the same as one reached gradually.",
  description_hi:
    "Donchian Channel teen lines plot karta: upper band `period` bars ka highest high, lower band lowest low, middle dono ka average. Smoothing nahi — naya high print ho to upper band turant step up; lower band ka same naya low pe.\n\nRichard Dennis ke 1980s Turtle Traders system se famous hua: 20-day high breakout pe long enter karo, 10-day low pe exit. Yeh ek rule futures pe apply karke legendary returns generate kiye. Kaam karta hai kyunki trending markets mein highest-high keep rising, har naya bar ek fresh entry signal; chop mein breakouts jaldi fail hote hain but loss channel width se bounded hai.\n\nDonchian OG breakout indicator hai. Bollinger aur Keltner se comparison:\n• Donchian: actual extremes se bounded hard rectangle (no math).\n• Bollinger: standard deviation pe based soft curve.\n• Keltner: ATR pe based soft curve.\n\nDonchian ki hardness visually intuitive aur backtest-friendly banati hai, but move ke 'how' ko ignore karta hai — single explosive bar pe pahuncha 20-day high gradually pahunche ke same read hota hai.",

  formula_explanation:
    "Upper = max(high) over last `period` bars. Lower = min(low) over last `period` bars. Middle = (Upper + Lower) / 2. Default period: 20. No smoothing, no parameters beyond the lookback length.",

  default_period: 20,
  period_range: [5, 200],
  common_periods: [10, 20, 55],

  use_cases: [
    {
      scenario: "Turtle-style breakout entry",
      what_to_do: "Enter long when price closes above the 20-day Donchian high; exit when it closes below the 10-day low",
      why: "Mechanically tested across decades and asset classes; the asymmetry between entry (20-day) and exit (10-day) is the original Turtle insight.",
    },
    {
      scenario: "Range identification",
      what_to_do: "If the Donchian upper and lower bands are flat for many bars, price is in a tight range — don't take breakout signals until they reactivate",
      why: "Flat channel means no new highs or lows = market memory-less = breakouts more likely to fail.",
    },
    {
      scenario: "Trailing stop in long positions",
      what_to_do: "Use the lower band of a shorter-period Donchian (e.g. 10-bar) as a trailing stop on long entries from the 20-bar breakout",
      why: "Asymmetric Donchian (wide entry, narrow exit) gives trends room to breathe while exiting cleanly when momentum fades.",
    },
  ],

  common_signals: [
    {
      signal: "Donchian upper breakout",
      condition: "Close exceeds the upper band (new period-high)",
      action: "Long entry candidate — classic trend-following.",
    },
    {
      signal: "Donchian lower breakdown",
      condition: "Close below the lower band (new period-low)",
      action: "Short entry / long exit candidate.",
    },
    {
      signal: "Donchian compression",
      condition: "Upper and lower bands flatten and narrow",
      action: "Volatility squeeze — prepare for breakout, stand aside until it triggers.",
    },
  ],

  pitfalls: [
    "Breakout signals work in trending markets and lose money in choppy ones — like all breakout systems, pair with a trend / volatility filter.",
    "On low-volume holidays or pre-event days, false breakouts spike because the daily range expands artificially.",
    "The hard rectangle hides the path — a 20-day high reached via a sharp spike on bar 1 reads identically to one reached on bar 20.",
    "Different periods produce very different signal frequency — period 10 fires often, period 55 (a Turtle setting) fires rarely.",
    "Doesn't work well on heavily-mean-reverting stocks like utilities or some FMCG names — designed for trending assets.",
  ],

  works_well_with: ["adx", "atr", "supertrend", "ema"],
  works_poorly_with: ["bollinger-bands", "keltner-channel", "standard-deviation"],

  example_strategies: [
    "Turtle Trader 20/10 Breakout (daily commodities + F&O)",
    "Donchian Breakout with ADX Filter (positional indices)",
    "55-Bar Donchian Long-Only Trend Catcher",
  ],

  indian_context:
    "Donchian is well-suited to Indian commodities (MCX gold, crude, copper) where trends are sustained and the original Turtle template ports almost unmodified. For NIFTY / BANKNIFTY, the 20-bar Donchian breakout is a common positional setup on the daily timeframe; intraday Donchian breakouts on F&O indices are noisier due to expiry-week distortion and OI rebalancing. NSE F&O stocks with strong recent trends (post-earnings, sector rotation) sometimes deliver 50-bar Donchian breakouts on the daily as multi-week momentum setups.",
};
