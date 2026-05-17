import type { MarketingTemplate } from "../_types";

export const PNL_STORY_TEMPLATE: MarketingTemplate = {
  slug: "instagram-pnl-story-template",
  platform: "instagram",
  use_case: "Story-format template for sharing paper P&L (24h ephemeral)",
  audience: "general",

  content_en: `Story slide 1 (background: subtle equity curve animation):
"This week on TradeTri paper accounts"

Story slide 2 (big numbers, centred):
"Median user: {{median_pnl_pct}}%
Top quartile: {{top_q_pnl_pct}}%
Bottom quartile: {{bottom_q_pnl_pct}}%"

Story slide 3 (caveat, smaller text):
"Past paper results don't predict live trading. Live is harder. We share both numbers — green and red."

Story slide 4 (CTA):
"Want to paper-trade for free? tradetri.com"

(Each slide 5-7 seconds. Use "swipe up" sticker only on the CTA slide.)
`,
  content_hi: `Story slide 1 (background: subtle equity curve animation):
"Is hafte TradeTri paper accounts pe"

Story slide 2 (big numbers, centred):
"Median user: {{median_pnl_pct}}%
Top quartile: {{top_q_pnl_pct}}%
Bottom quartile: {{bottom_q_pnl_pct}}%"

Story slide 3 (caveat, smaller text):
"Past paper results live trading predict nahi karte. Live harder hai. Hum dono numbers share karte — green aur red."

Story slide 4 (CTA):
"Free paper-trade karna? tradetri.com"

(Har slide 5-7 second. "Swipe up" sticker sirf CTA slide pe.)
`,

  required_vars: ["median_pnl_pct", "top_q_pnl_pct", "bottom_q_pnl_pct"],
  cta: "Visit tradetri.com",
  estimated_chars: 700,
  visuals_suggested: [
    "Brand-coloured background gradients per slide",
    "Slide 2: 64-pt numbers, sans-serif, high contrast",
    "Slide 3: smaller serif text to feel like a footnote, not bury the caveat",
  ],
};
