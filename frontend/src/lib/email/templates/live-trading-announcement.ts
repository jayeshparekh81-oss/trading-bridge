import type { EmailTemplate } from "./_types";

export const LIVE_TRADING_ANNOUNCEMENT: EmailTemplate = {
  slug: "live-trading-announcement",
  name: "Live trading feature unlock (per-user gate)",
  category: "welcome",

  subject_en: "Live trading is now unlocked for your TradeTri account",
  subject_hi: "Aapke TradeTri account ke liye live trading ab unlocked hai",

  body_en: `Hi {{user_name}},

Based on your paper trading track record ({{paper_days}} days, {{paper_trades}} trades, {{paper_pnl_pct}}% P&L), live trading is now unlocked on your TradeTri account.

WHAT CHANGES

You can now place real orders through your connected broker. Until now, your strategies were running in paper mode (no real money moving). You can keep paper-trading new strategies AND run live ones simultaneously — they're independent.

WHAT TO DO FIRST

1. START SMALL. Run live with ₹25,000-₹50,000 max for the first 4 weeks, no matter how confident your paper results made you.
2. RUN ONLY ONE STRATEGY LIVE initially. Multi-strategy live trading has more interaction risk than paper testing reveals.
3. KEEP YOUR PAPER ACCOUNT RUNNING IN PARALLEL. The paper P&L of the same strategy is your benchmark for whether live is working as expected — if live deviates from paper by more than 25%, there's a slippage or execution issue.
4. SET A WEEKLY DRAWDOWN CIRCUIT-BREAKER. If live loses more than 5% in a week, pause all strategies and reassess. This is a hard rule, not a suggestion.

LIMITATIONS AND DISCLAIMERS

• Live trading involves real risk of capital loss. Past paper performance does NOT guarantee live performance.
• Indian F&O has additional risks (overnight gap, expiry whipsaws) that paper backtests may underestimate.
• TradeTri is a tools provider, not an investment advisor. We do not guarantee any returns and you are responsible for every order placed through your account.

If you'd like to pause live and stay on paper, just toggle the strategy back to paper mode in the dashboard. No penalty, no questions.

{{dashboard_url}}

— Team TradeTri
`,
  body_hi: `Namaste {{user_name}},

Aapke paper trading track record ({{paper_days}} din, {{paper_trades}} trades, {{paper_pnl_pct}}% P&L) ke base pe, live trading aapke TradeTri account pe ab unlocked hai.

KYA CHANGE HOTA HAI

Aap ab connected broker se real orders place kar sakte hain. Abhi tak aapki strategies paper mode mein chal rahi thin (koi real paisa nahi). Aap naye strategies paper-trade karte rah sakte hain AND live ones simultaneously chala sakte hain — independent hain.

PEHLE KYA KAREIN

1. CHHOTE SE START KAREIN. Pehle 4 hafte live ke liye ₹25,000-₹50,000 maximum chalayein, paper results se chahe kitna bhi confident kyun na ho.
2. INITIALLY EK HI STRATEGY LIVE CHALAYEIN. Multi-strategy live trading mein paper testing se zyada interaction risk hota.
3. PAPER ACCOUNT PARALLEL CHALU RAKHEIN. Same strategy ka paper P&L aapka benchmark hai — live paper se 25% se zyada deviate kare to slippage ya execution issue hai.
4. WEEKLY DRAWDOWN CIRCUIT-BREAKER SET KAREIN. Live mein hafte mein 5% se zyada loss ho to sab strategies pause karke reassess karein. Hard rule hai, suggestion nahi.

LIMITATIONS AUR DISCLAIMERS

• Live trading mein real capital loss ka risk hai. Past paper performance live performance ki GUARANTEE NAHI deta.
• Indian F&O mein additional risks hain (overnight gap, expiry whipsaws) jo paper backtests underestimate kar sakte hain.
• TradeTri tools provider hai, investment advisor nahi. Hum koi returns guarantee nahi karte aur aap apne account se place hue har order ke liye responsible hain.

Live pause karke wapas paper pe rehna ho to dashboard mein strategy ko paper mode mein toggle kar dein. Koi penalty nahi, koi sawaal nahi.

{{dashboard_url}}

— Team TradeTri
`,

  required_vars: [
    "user_name",
    "paper_days",
    "paper_trades",
    "paper_pnl_pct",
    "dashboard_url",
  ],
};
