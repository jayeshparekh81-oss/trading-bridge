import type { MarketingTemplate } from "../_types";

export const PRICING_REVEAL: MarketingTemplate = {
  slug: "twitter-pricing-reveal",
  platform: "twitter",
  use_case: "Pricing announcement tweet — flat fee, no profit share, no per-trade",
  audience: "general",

  content_en: `TradeTri pricing, finalised:

• Paper trading: FREE forever
• Live trading: ₹{{monthly_fee}}/month flat
• No per-trade fee
• No profit share
• No setup fee
• 60-day money-back

Why flat? Because per-trade and profit-share pricing both create incentives for the platform to push more trades or claim more credit for your wins. Flat means we make money only if you find us useful enough to keep paying.

That's it. {{pricing_page_url}}
`,
  content_hi: `TradeTri pricing, final:

• Paper trading: FREE hamesha
• Live trading: ₹{{monthly_fee}}/mahina flat
• Per-trade fee nahi
• Profit share nahi
• Setup fee nahi
• 60-day money-back

Flat kyun? Kyunki per-trade aur profit-share dono platform ko incentive dete zyada trades push karne ya aapki wins ka credit lene ke. Flat ka matlab hum tabhi paise kamaate jab aap hamein useful samjho aur pay karte raho.

Bas. {{pricing_page_url}}
`,

  required_vars: ["monthly_fee", "pricing_page_url"],
  cta: "See full pricing: {{pricing_page_url}}",
  estimated_chars: 600,
  visuals_suggested: [
    "Pricing card with all 4 'no' points called out in bold",
    "Comparison table: TradeTri flat vs typical broker AMC vs typical paid signal service",
  ],
};
