import type { EmailTemplate } from "./_types";

export const WEEKLY_DIGEST: EmailTemplate = {
  slug: "weekly-digest",
  name: "Weekly performance digest (every Sunday 8 AM IST)",
  category: "digest",

  subject_en: "Your TradeTri week: {{week_pnl_pct}}% paper P&L, {{trade_count}} trades",
  subject_hi: "Aapka TradeTri hafta: {{week_pnl_pct}}% paper P&L, {{trade_count}} trades",

  body_en: `Hi {{user_name}},

Here's your week at a glance ({{week_start_date}} to {{week_end_date}}):

PERFORMANCE
• Paper P&L: {{week_pnl_pct}}% ({{week_pnl_inr}})
• Trades taken: {{trade_count}}
• Win rate: {{win_rate_pct}}%
• Best strategy: {{best_strategy_name}} ({{best_strategy_pnl_pct}}%)
• Worst strategy: {{worst_strategy_name}} ({{worst_strategy_pnl_pct}}%)

THIS WEEK'S MARKET
{{market_context_blurb}}

WHAT TO REVIEW
• Have any strategies underperformed for 3+ weeks? Pause them.
• Are you over-concentrated in one sector? Diversify.
• Did you override a signal manually? Note WHY in your trading journal.

{{dashboard_url}}

— Team TradeTri
`,
  body_hi: `Namaste {{user_name}},

Yahan aapka hafta ek nazar mein hai ({{week_start_date}} se {{week_end_date}}):

PERFORMANCE
• Paper P&L: {{week_pnl_pct}}% ({{week_pnl_inr}})
• Trades liye: {{trade_count}}
• Win rate: {{win_rate_pct}}%
• Best strategy: {{best_strategy_name}} ({{best_strategy_pnl_pct}}%)
• Worst strategy: {{worst_strategy_name}} ({{worst_strategy_pnl_pct}}%)

IS HAFTE KA MARKET
{{market_context_blurb}}

KYA REVIEW KAREIN
• Koi strategy 3+ weeks underperform kar rahi hai? Pause kar dein.
• Ek sector mein over-concentrated to nahi? Diversify karein.
• Manually koi signal override kiya? Trading journal mein KYUN likhein.

{{dashboard_url}}

— Team TradeTri
`,

  required_vars: [
    "user_name",
    "week_start_date",
    "week_end_date",
    "week_pnl_pct",
    "week_pnl_inr",
    "trade_count",
    "win_rate_pct",
    "best_strategy_name",
    "best_strategy_pnl_pct",
    "worst_strategy_name",
    "worst_strategy_pnl_pct",
    "market_context_blurb",
    "dashboard_url",
  ],
};
