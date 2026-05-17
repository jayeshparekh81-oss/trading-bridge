import type { MarketingTemplate } from "../_types";

export const STRATEGY_SUGGESTION: MarketingTemplate = {
  slug: "whatsapp-strategy-suggestion",
  platform: "whatsapp",
  use_case: "Suggest a strategy template based on user's current paper-trading profile",
  audience: "active_user",

  content_en: `Hi {{user_name}},

Quick suggestion based on your account:

Your {{current_strategy_name}} has run {{strategy_days}} days. It's averaging {{current_strategy_pnl_pct}}% with a win rate of {{win_rate_pct}}%.

You might want to ALSO paper-trade {{suggested_strategy_name}}. Why: {{suggestion_reason}}.

This isn't a tip. It's a "based on your style, this template often pairs well" nudge.

Open it: {{suggested_strategy_url}}

Ignore this if you'd rather stay focused on one strategy — that's also valid.

— TradeTri
`,
  content_hi: `Namaste {{user_name}},

Aapke account ke base pe ek quick suggestion:

Aapka {{current_strategy_name}} {{strategy_days}} din chala. Average {{current_strategy_pnl_pct}}%, win rate {{win_rate_pct}}%.

Aap ek aur strategy paper-trade kar sakte: {{suggested_strategy_name}}. Kyun: {{suggestion_reason_hi}}.

Ye tip nahi hai. Ye "aapki style ke hisaab se ye template often pair karta hai" nudge hai.

Khole: {{suggested_strategy_url}}

Ek hi strategy pe focus rehna chahein to ignore karein — wo bhi valid hai.

— TradeTri
`,

  required_vars: [
    "user_name",
    "current_strategy_name",
    "strategy_days",
    "current_strategy_pnl_pct",
    "win_rate_pct",
    "suggested_strategy_name",
    "suggestion_reason",
    "suggestion_reason_hi",
    "suggested_strategy_url",
  ],
  cta: "Open {{suggested_strategy_name}}: {{suggested_strategy_url}}",
  estimated_chars: 800,
  visuals_suggested: [
    "Small comparison card: current vs suggested strategy (win rate, R:R, difficulty)",
  ],
};
