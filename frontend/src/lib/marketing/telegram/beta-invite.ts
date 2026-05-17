import type { MarketingTemplate } from "../_types";

export const BETA_INVITE: MarketingTemplate = {
  slug: "telegram-beta-invite",
  platform: "telegram",
  use_case: "Live trading beta cohort invite (selected vetted accounts)",
  audience: "active_user",

  content_en: `**You're invited: TradeTri Live Beta** 🔓

Hi {{user_name}}, you're one of {{cohort_size}} traders we're inviting to the first wave of live trading on TradeTri.

WHY YOU:
Your paper account has run {{paper_days}} days with {{paper_pnl_pct}}% returns, {{trade_count}} trades, and a max drawdown of {{max_dd_pct}}%. That's the consistency profile we trust to go live first.

THE BETA TERMS:
• Live trading unlocked for ₹{{max_capital}} starting capital cap
• ₹{{monthly_fee}}/month flat (no per-trade, no profit share)
• Weekly check-in call with our team (optional)
• Full audit log access — you can see every single signal and order
• 60-day money-back if you change your mind

WHAT WE NEED FROM YOU:
• Hard stop on first-month live capital at ₹{{max_capital}}
• Honest feedback on what breaks or surprises you
• Pause if you hit -5% weekly drawdown (we enforce this server-side)

Want in? Reply YES and we'll send onboarding details.
`,
  content_hi: `**Aap invited hain: TradeTri Live Beta** 🔓

Namaste {{user_name}}, {{cohort_size}} traders mein se ek aap hain jinhe hum TradeTri live trading ke pehle wave ke liye invite kar rahe.

AAP HI KYUN:
Aapka paper account {{paper_days}} din chala, {{paper_pnl_pct}}% returns, {{trade_count}} trades, max drawdown {{max_dd_pct}}%. Yahi consistency profile hai jise hum pehle live karne ke liye trust karte.

BETA TERMS:
• Live trading unlock ₹{{max_capital}} starting capital cap pe
• ₹{{monthly_fee}}/mahina flat (per-trade nahi, profit share nahi)
• Hamare team ke saath weekly check-in call (optional)
• Full audit log access — har signal aur order dekh sakte ho
• 60-day money-back agar mann badle

HUM KYA EXPECT KARTE HAIN:
• Pehle mahine ka live capital ₹{{max_capital}} se zyada nahi
• Kya break ya surprise hota hai — honest feedback
• -5% weekly drawdown hit ho to pause (hum server-side enforce karte)

Interested? YES reply karein, onboarding details bhejenge.
`,

  required_vars: [
    "user_name",
    "cohort_size",
    "paper_days",
    "paper_pnl_pct",
    "trade_count",
    "max_dd_pct",
    "max_capital",
    "monthly_fee",
  ],
  cta: "Reply YES to claim beta slot",
  estimated_chars: 1300,
  visuals_suggested: [
    "Personalised paper-performance card (user's actual numbers)",
    "Short founder video explaining beta philosophy",
  ],
};
