import type { EmailTemplate } from "./_types";

export const PAPER_MILESTONE: EmailTemplate = {
  slug: "paper-milestone",
  name: "Paper trading milestone reached (e.g. 4 weeks, 100 trades)",
  category: "nudge",

  subject_en: "Milestone hit: {{milestone_label}} — {{paper_pnl_pct}}% paper P&L",
  subject_hi: "Milestone hit: {{milestone_label}} — {{paper_pnl_pct}}% paper P&L",

  body_en: `Hi {{user_name}},

You've reached a paper trading milestone: {{milestone_label}}.

Your stats so far:
• Paper P&L: {{paper_pnl_pct}}% over {{tracking_days}} days
• Trades taken: {{trade_count}}
• Win rate: {{win_rate_pct}}%
• Worst drawdown: {{max_drawdown_pct}}%
• Sharpe (rough): {{sharpe_rough}}

WHAT THIS MEANS

This is enough data to start drawing conclusions about whether YOUR specific setup works for YOUR personality. But:

• If your max drawdown is more than 15%, the live version will hurt more emotionally than paper did. Consider reducing position size or pausing the riskiest strategy.
• If you've overridden the system manually more than 20% of the time, you're paper-trading discretion, not the strategy. Either commit to the rules OR document a clear override policy.
• A 4-week paper P&L of 5-15% is realistic. Anything dramatically higher likely won't repeat — markets regress to the mean.

WHEN TO GO LIVE

We don't tell you when. But the typical pattern: 8-12 weeks paper → small live capital (₹25k-50k) → scale only after 3+ months of stable live performance.

{{dashboard_url}}

— Team TradeTri
`,
  body_hi: `Namaste {{user_name}},

Aap ne paper trading milestone reach kiya: {{milestone_label}}.

Aapki stats ab tak:
• Paper P&L: {{paper_pnl_pct}}% over {{tracking_days}} din
• Trades liye: {{trade_count}}
• Win rate: {{win_rate_pct}}%
• Worst drawdown: {{max_drawdown_pct}}%
• Sharpe (rough): {{sharpe_rough}}

ISKA MATLAB

Itna data enough hai conclusions draw karne ke liye ki AAPKA specific setup AAPKI personality ke saath kaam karta hai ya nahi. But:

• Max drawdown 15% se zyada hai to live version paper se zyada emotionally hurt karega. Position size reduce karein ya sabse risky strategy pause karein.
• 20% se zyada baar system override manually kiya to aap paper-trading discretion kar rahe, strategy nahi. Either rules pe commit karein OR clear override policy document karein.
• 4-hafte ka paper P&L 5-15% realistic hai. Dramatically higher kuch bhi repeat shayad nahi hoga — markets mean ki taraf regress karte.

LIVE KAB JAAYEN

Hum nahi batayenge kab. But typical pattern: 8-12 weeks paper → small live capital (₹25k-50k) → 3+ months stable live performance ke baad scale.

{{dashboard_url}}

— Team TradeTri
`,

  required_vars: [
    "user_name",
    "milestone_label",
    "paper_pnl_pct",
    "tracking_days",
    "trade_count",
    "win_rate_pct",
    "max_drawdown_pct",
    "sharpe_rough",
    "dashboard_url",
  ],
};
