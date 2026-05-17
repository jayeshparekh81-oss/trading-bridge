import type { IndicatorContent } from "./_types";

export const STANDARD_ERROR_CHANNEL: IndicatorContent = {
  slug: "standard-error-channel",
  name: "Standard Error Channel",
  category: "trend",
  complexity: "advanced",

  one_liner_en:
    "Linear regression with bands based on standard error (not standard deviation) — tighter than regression channel, more responsive to volatility changes.",
  one_liner_hi:
    "Linear regression bands ke saath standard error pe based (standard deviation nahi) — regression channel se tighter, volatility changes ke zyada responsive.",

  description_en:
    "The Standard Error Channel is a refinement of the Linear Regression Channel that uses STANDARD ERROR instead of standard deviation for its band width. The distinction matters: standard deviation measures how spread out the data is; standard error measures how confident we are in the fitted line itself. SE-based bands shrink as the trend becomes more reliable and widen when the trend gets noisier.\n\nIn practice, Standard Error Channels are usually NARROWER than Linear Regression Channels for the same data, especially in clean trends. The narrower bands give earlier signals (sooner band touches) but also more false positives. Traders who like aggressive entries near band edges prefer SE channels; conservative traders prefer regression channels.\n\nThe trade rules are similar to Linear Regression Channels: mean reversion to the regression line on band touches, with the regression line itself as the target. The difference is mostly cosmetic for the signal logic but can be substantial for risk management — narrower bands mean tighter stops are appropriate.\n\nFor Indian retail, Standard Error Channels work well on NIFTY F&O during stable trend regimes where the trend's reliability allows the SE bands to tighten meaningfully. In choppy markets, the SE bands widen so much that they lose signal value.",
  description_hi:
    "Standard Error Channel Linear Regression Channel ka refinement hai jo apne band width ke liye standard deviation ki jagah STANDARD ERROR use karta. Distinction matter karta: standard deviation data kitna spread hai measure karta; standard error fitted line mein hum kitne confident hain measure karta. SE-based bands shrink hote jaise trend more reliable hota aur widen hote jaise trend noisier.\n\nPractice mein, Standard Error Channels usually same data ke liye Linear Regression Channels se NARROWER hote, especially clean trends mein. Narrower bands earlier signals dete (sooner band touches) but more false positives bhi. Aggressive entries band edges ke paas prefer karne wale traders SE channels prefer karte; conservative traders regression channels.\n\nTrade rules Linear Regression Channels ke similar: band touches pe regression line ki mean reversion, regression line khud target ke roop mein. Signal logic ke liye difference mostly cosmetic hai but risk management ke liye substantial ho sakta — narrower bands matlab tighter stops appropriate.\n\nIndian retail ke liye, Standard Error Channels NIFTY F&O pe stable trend regimes mein achha kaam karte jahan trend ki reliability SE bands ko meaningfully tighten allow karti. Choppy markets mein SE bands itne widen ho jaate ki signal value lose ho jaata.",

  formula_explanation:
    "Step 1: Fit OLS regression line through last N bars. Step 2: Compute Standard Error = sqrt(sum_of_residuals^2 / (N - 2)). Step 3: Upper band = fitted_line + k × SE; Lower band = fitted_line - k × SE. Multiplier k is typically 1.5 or 2. SE is smaller than standard deviation σ when the regression fit is good; it diverges from σ when residuals have systematic patterns (curved trend, regime change).",

  default_period: 20,
  period_range: [10, 100],
  common_periods: [20, 50],

  use_cases: [
    {
      scenario: "Tight-stop mean reversion in clean trends",
      what_to_do: "Long at lower SE band with stop just below; target regression line",
      why: "Narrower bands than regression channel give earlier entries at lower risk per trade in clean trend regimes.",
    },
    {
      scenario: "Detecting when a trend is degrading",
      what_to_do: "Watch SE band width — sudden widening signals trend is becoming less reliable",
      why: "SE bands measure trend confidence, not just price spread; widening bands directly indicate trend quality degradation.",
    },
    {
      scenario: "Comparing trend quality across instruments",
      what_to_do: "Lower SE relative to price = more reliable trend; rank instruments for trend-following entries",
      why: "SE-based ranking finds the highest-quality trend setups across a basket of instruments.",
    },
  ],

  common_signals: [
    {
      signal: "Lower SE band buy",
      condition: "Price touches lower band in established uptrend with tight SE",
      action: "Long entry candidate with tight stop below band.",
    },
    {
      signal: "Upper SE band sell",
      condition: "Price touches upper band in established downtrend with tight SE",
      action: "Short entry candidate with tight stop above band.",
    },
    {
      signal: "Trend degradation warning",
      condition: "SE bands widening significantly while price stays inside",
      action: "Trend quality degrading; tighten risk management.",
    },
    {
      signal: "Trend break",
      condition: "Price closes outside SE band against the trend direction",
      action: "Trend regime change probable; exit trend trades.",
    },
  ],

  pitfalls: [
    "Narrower bands = more false signals in choppy markets — pair with ADX filter.",
    "Standard error is statistically sensitive to outliers; gap moves can distort SE readings.",
    "Period choice critical — too short = noisy SE, too long = stale SE.",
    "Confusion with Linear Regression Channel — visually similar but mathematically distinct.",
    "Tight bands tempting to fade aggressively; respect ATR-based stops, not just band-based.",
  ],

  works_well_with: ["adx", "ema", "atr", "supertrend"],
  works_poorly_with: ["bollinger-bands", "standard-deviation", "linear-regression-channel"],

  example_strategies: [
    "Standard Error mean reversion on NIFTY daily clean trends",
    "Trend quality scanner across NIFTY 100 using SE rankings",
    "SE-band tight-stop swing trading on F&O cash equity",
  ],

  indian_context:
    "Standard Error Channels on NIFTY daily during 2023 H2 rally and 2024 pre-budget rally showed exceptionally tight SE bands — a sign of high-quality trend. During the 2022 ranging year, SE bands widened so much they became unusable. BANKNIFTY's higher volatility creates wider SE bands than NIFTY's; useful for swing traders who want to ride the bigger moves. For F&O cash equity, SE channels work best on RIL, ICICI Bank during sustained sector trends. The 'SE band width' metric is useful for cross-stock trend quality comparison — pick the cleanest trends, not necessarily the strongest.",
};
