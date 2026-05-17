import type { EmailTemplate } from "./_types";

export const FIRST_STRATEGY_NUDGE: EmailTemplate = {
  slug: "first-strategy-nudge",
  name: "First strategy nudge (D+3 if no strategy started)",
  category: "nudge",

  subject_en: "Pick your first strategy — 3 minutes, no commitment",
  subject_hi: "Apni pehli strategy choose karein — 3 minutes, koi commitment nahi",

  body_en: `Hi {{user_name}},

We noticed you signed up 3 days ago but haven't started a strategy yet. Totally fine — we don't push people who aren't ready.

But if you want to take a 3-minute look, here are the two simplest beginner templates:

• EMA Crossover (9/21): the cleanest momentum entry. Win rate ~52%, monthly paper returns 2-4%.
• RSI Oversold Bounce: mean-reversion when stocks dip. Win rate ~55%, monthly paper returns 2-5%.

Both are paper-trade-only until you flip the switch. Zero capital risk.

{{strategy_explorer_url}}

If you'd rather wait, no worries. Reply with any question and we'll help you pick something that fits.

— Team TradeTri
`,
  body_hi: `Namaste {{user_name}},

Hum ne notice kiya ki aap 3 din pehle signup kiye but abhi tak strategy start nahi ki. Bilkul theek hai — hum ready nahi log ko push nahi karte.

Lekin agar 3 minute look karna ho, do simplest beginner templates ye hain:

• EMA Crossover (9/21): cleanest momentum entry. Win rate ~52%, monthly paper returns 2-4%.
• RSI Oversold Bounce: mean-reversion jab stocks dip karte. Win rate ~55%, monthly paper returns 2-5%.

Dono paper-trade-only hain jab tak aap switch flip na karein. Zero capital risk.

{{strategy_explorer_url}}

Wait karna chahein to no problem. Koi question ho to reply kar dein, hum help karenge.

— Team TradeTri
`,

  required_vars: ["user_name", "strategy_explorer_url"],
};
