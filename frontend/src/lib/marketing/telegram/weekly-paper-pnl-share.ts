import type { MarketingTemplate } from "../_types";

export const WEEKLY_PAPER_PNL_SHARE: MarketingTemplate = {
  slug: "telegram-weekly-paper-pnl-share",
  platform: "telegram",
  use_case: "Weekly community paper-trading roundup (Mondays)",
  audience: "general",

  content_en: `**Paper P&L this week** 📊
{{week_label}}

Across {{active_user_count}} active paper users:
• Median weekly P&L: {{median_pnl_pct}}%
• Top quartile: {{top_q_pnl_pct}}%
• Bottom quartile: {{bottom_q_pnl_pct}}%
• Best strategy this week: {{best_strategy_name}} ({{best_strategy_pnl_pct}}% median)
• Worst strategy this week: {{worst_strategy_name}} ({{worst_strategy_pnl_pct}}% median)

Honest note: these are PAPER results in {{market_regime}}. Live performance after slippage and emotions is meaningfully lower. We share both numbers — not just the green ones.

Want to see the full breakdown by strategy and timeframe?
{{leaderboard_url}}
`,
  content_hi: `**Is hafte ka paper P&L** 📊
{{week_label}}

{{active_user_count}} active paper users mein:
• Median weekly P&L: {{median_pnl_pct}}%
• Top quartile: {{top_q_pnl_pct}}%
• Bottom quartile: {{bottom_q_pnl_pct}}%
• Best strategy is hafte: {{best_strategy_name}} ({{best_strategy_pnl_pct}}% median)
• Worst strategy is hafte: {{worst_strategy_name}} ({{worst_strategy_pnl_pct}}% median)

Honest baat: ye PAPER results hain {{market_regime}} mein. Live performance slippage aur emotions ke baad meaningfully kam hota. Hum dono numbers share karte hain — sirf green wale nahi.

Strategy aur timeframe ke hisaab se full breakdown chahiye?
{{leaderboard_url}}
`,

  required_vars: [
    "week_label",
    "active_user_count",
    "median_pnl_pct",
    "top_q_pnl_pct",
    "bottom_q_pnl_pct",
    "best_strategy_name",
    "best_strategy_pnl_pct",
    "worst_strategy_name",
    "worst_strategy_pnl_pct",
    "market_regime",
    "leaderboard_url",
  ],
  cta: "See full leaderboard at {{leaderboard_url}}",
  estimated_chars: 950,
  visuals_suggested: [
    "Horizontal bar chart of top 5 vs bottom 5 strategies",
    "Distribution histogram of user weekly P&L",
    "NIFTY chart with the week's range annotated for context",
  ],
};
