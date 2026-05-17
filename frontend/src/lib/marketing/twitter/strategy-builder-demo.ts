import type { MarketingTemplate } from "../_types";

export const STRATEGY_BUILDER_DEMO: MarketingTemplate = {
  slug: "twitter-strategy-builder-demo",
  platform: "twitter",
  use_case: "Standalone tweet showing strategy builder demo (with GIF/video)",
  audience: "general",

  content_en: `Demo: building an EMA crossover strategy in 47 seconds on TradeTri.

No code. No spreadsheets. No Python.

You pick the indicators, set the rules, click backtest, and paper-trade.

The same engine that powers our live trading is the one running the backtest — so what you see is what you'll get.

{{demo_url}}
`,
  content_hi: `Demo: TradeTri pe 47 seconds mein EMA crossover strategy banaate.

Code nahi. Spreadsheets nahi. Python nahi.

Indicators choose karo, rules set karo, backtest click karo, paper-trade karo.

Jo engine hamare live trading ko power karta hai wahi backtest bhi chalata — to jo dekhte ho wahi milta.

{{demo_url}}
`,

  required_vars: ["demo_url"],
  cta: "Watch demo: {{demo_url}}",
  estimated_chars: 350,
  visuals_suggested: [
    "30-45 sec screen recording of strategy builder",
    "Speed-up the boring parts (fields filling), real-time the moment of clicking Backtest",
    "End frame with TradeTri logo + URL",
  ],
};
