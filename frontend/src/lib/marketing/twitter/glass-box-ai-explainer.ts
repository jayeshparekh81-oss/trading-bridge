import type { MarketingTemplate } from "../_types";

export const GLASS_BOX_AI_EXPLAINER: MarketingTemplate = {
  slug: "twitter-glass-box-ai-explainer",
  platform: "twitter",
  use_case: "Standalone explainer tweet on Glass Box AI — our auditable indicator engine",
  audience: "general",

  content_en: `"Glass Box" is what we call our indicator engine.

Every RSI, EMA, MACD calculation on TradeTri is auditable. You click any value, you see the formula, the inputs, the bar timestamps used, and you can verify on your broker's chart.

Why? Because the alternative — black-box "AI signals" that you can't verify — is how Indian retail trading got the bad reputation it has.

We owe customers transparency, not magic.

{{audit_log_demo_url}}
`,
  content_hi: `"Glass Box" hamare indicator engine ka naam hai.

TradeTri pe har RSI, EMA, MACD calculation auditable hai. Koi bhi value click karo, formula, inputs, bar timestamps dikh jaayenge, aur apne broker ke chart pe verify kar sakte.

Kyun? Kyunki alternative — black-box "AI signals" jo verify nahi kar sakte — yahi Indian retail trading ke bad reputation ka reason hai.

Hum customers ko transparency dete hain, magic nahi.

{{audit_log_demo_url}}
`,

  required_vars: ["audit_log_demo_url"],
  cta: "See an audit log: {{audit_log_demo_url}}",
  estimated_chars: 600,
  visuals_suggested: [
    "Screenshot: indicator value clicked, audit panel expanded showing formula+inputs",
    "Side-by-side: TradeTri value vs Kite chart same indicator, identical numbers",
  ],
};
