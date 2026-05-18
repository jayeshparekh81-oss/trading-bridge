import type { IndicatorContent } from "./_types";

export const LINEAR_REGRESSION_CHANNEL: IndicatorContent = {
  slug: "linear-regression-channel",
  name: "Linear Regression Channel",
  category: "trend",
  complexity: "intermediate",

  one_liner_en:
    "A regression line through recent prices with parallel bands at ±N standard deviations — visualizes trend slope and statistical extremes.",
  one_liner_hi:
    "Recent prices ke through regression line ±N standard deviations pe parallel bands ke saath — trend slope aur statistical extremes visualize karta.",

  description_en:
    "The Linear Regression Channel takes a moving window of recent prices and fits the BEST STRAIGHT LINE through them using ordinary least squares. The slope of that line is the trend; the line itself is the 'fair value' along that trend. Parallel bands above and below at N standard deviations of the residuals create a statistical channel.\n\nUnlike a moving average which is a SMOOTHED price, a regression line is the LINEAR FIT. The difference matters: regression projects forward (you can extend the line into the future), gives you trend direction explicitly (the slope), and offers natural statistical extremes (the deviation bands).\n\nTrade rules vary, but the classic use is mean reversion to the regression line: when price hits the upper +2σ band, sell; lower -2σ band, buy. The line itself is the target for both directions. This works in TRENDING markets that respect the channel boundaries — different from Bollinger Bands which work best in ranging markets.\n\nFor Indian retail, Linear Regression Channels on NIFTY daily during clear trend phases (multi-week directional moves) provide both entry timing (band touches) and exit timing (regression line crossover). The channel's projection ability also helps with setting realistic targets.",
  description_hi:
    "Linear Regression Channel recent prices ke ek moving window leta aur ordinary least squares se BEST STRAIGHT LINE fit karta. Us line ka slope trend hai; line khud trend ke along 'fair value' hai. Bands upar aur neeche residuals ke N standard deviations pe parallel bana ke statistical channel banate.\n\nMoving average jo SMOOTHED price hota uske unlike, regression line LINEAR FIT hai. Difference matter karta: regression forward project karta (line ko future mein extend kar sakte), trend direction explicitly deta (slope), aur natural statistical extremes deta (deviation bands).\n\nTrade rules vary karte, but classic use regression line ki mean reversion hai: jab price upper +2σ band hit kare to sell; lower -2σ band pe buy. Line khud dono directions ka target hai. Ye TRENDING markets mein kaam karta jo channel boundaries respect karte — Bollinger Bands se different jo ranging markets mein best kaam karte.\n\nIndian retail ke liye, Linear Regression Channels NIFTY daily pe clear trend phases (multi-week directional moves) mein entry timing (band touches) aur exit timing (regression line crossover) dono dete. Channel ki projection ability realistic targets set karne mein bhi help karti.",

  formula_explanation:
    "Step 1: Fit ordinary least squares line y = mx + b through the last N closing prices (typically N=20 or 50). Step 2: Compute residuals (actual - fitted) for each bar. Step 3: Compute standard deviation σ of residuals. Step 4: Upper band = fitted_line + Nσ, Lower band = fitted_line - Nσ (typically N=2). Step 5: Project line forward if needed by extending the slope from the last point. Common periods: 20, 50, 100.",

  default_period: 20,
  period_range: [10, 100],
  common_periods: [20, 50, 100],

  use_cases: [
    {
      scenario: "Mean reversion within an established uptrend channel",
      what_to_do: "Long when price touches lower -2σ band; target the regression line itself",
      why: "Trend-respecting mean reversion has higher hit rate than absolute price-based mean reversion because the channel adapts to the trend slope.",
    },
    {
      scenario: "Trend exhaustion detection",
      what_to_do: "When price breaks DOWN through the regression line within an uptrend channel, the trend may be ending",
      why: "Regression-line break is an earlier exhaustion signal than waiting for the lower band breach; gives time to exit gracefully.",
    },
    {
      scenario: "Setting realistic profit targets",
      what_to_do: "Use the +2σ band as a profit target for long entries near the line",
      why: "Targets based on the trend's own statistical channel are more realistic than fixed percentage targets.",
    },
  ],

  common_signals: [
    {
      signal: "Lower band buy",
      condition: "Price touches lower -2σ band in established uptrend",
      action: "Long entry candidate; target = regression line.",
    },
    {
      signal: "Upper band sell",
      condition: "Price touches upper +2σ band in established downtrend",
      action: "Short entry candidate; target = regression line.",
    },
    {
      signal: "Trend reversal",
      condition: "Price closes outside the channel against the trend direction",
      action: "Trend regime change starting; exit current trend trades.",
    },
    {
      signal: "Slope flip",
      condition: "Regression line slope changes sign (positive to negative or vice versa)",
      action: "Major trend bias shift; rebalance positions.",
    },
  ],

  pitfalls: [
    "Channel width changes daily as new bars roll in — entries that worked yesterday may not be available today.",
    "Strong trends can keep price OUTSIDE one band for many bars — fading band touches in such cases is a losing strategy.",
    "Period choice (20 vs 50 vs 100) dramatically changes the channel — choose based on holding period.",
    "Linear regression assumes the trend is linear — curved trends produce poor channel fits.",
    "Confusion with Bollinger Bands — both have bands but use different mathematics and work in different regimes.",
  ],

  works_well_with: ["adx", "ema", "supports-resistances", "rsi"],
  works_poorly_with: ["bollinger-bands", "standard-deviation"],

  example_strategies: [
    "Linear regression channel mean reversion on trending NIFTY daily",
    "Channel-target swing trades on F&O cash equity",
    "Trend exhaustion overlay on positional longs",
  ],

  indian_context:
    "Linear Regression Channels on NIFTY daily during sustained directional trends can provide intra-trend entry timing — band touches against the trend direction are the swing-entry zones, the regression line is the target. The 50-period channel is the workhorse for swing trades; 20-period is too noisy for daily, 100-period too slow. BANKNIFTY's higher volatility means wider channels — band touches happen more often, requiring stricter confirmation candles for entries. For F&O equity, regression channels work well on RIL, INFY in clear trend phases; less effective on choppy small-caps where the linear fit is poor.",
};
