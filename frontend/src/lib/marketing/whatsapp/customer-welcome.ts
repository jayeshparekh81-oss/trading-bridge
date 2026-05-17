import type { MarketingTemplate } from "../_types";

export const CUSTOMER_WELCOME: MarketingTemplate = {
  slug: "whatsapp-customer-welcome",
  platform: "whatsapp",
  use_case: "WhatsApp welcome message on signup (short, friendly, opt-in)",
  audience: "new_user",

  content_en: `Hi {{user_name}}! 👋

This is TradeTri on WhatsApp. You signed up earlier today — welcome.

Three things to know:
1. Your account is in paper-trading mode (no real money). That's the default and it stays free forever.
2. Live trading opens later — we'll let you know when.
3. We won't spam. You'll hear from us only for: token-expiry reminders, weekly digest (opt-in), and major product updates.

Need help? Just reply here. A human reads every message.

— TradeTri team
`,
  content_hi: `Namaste {{user_name}}! 👋

Ye TradeTri WhatsApp pe. Aaj signup kiya — welcome.

Teen baatein:
1. Aapka account paper-trading mode mein hai (real paisa nahi). Default ye hai aur free hamesha.
2. Live trading baad mein khulegi — hum bata denge.
3. Hum spam nahi karenge. Aap hamse sirf in cases mein sunenge: token-expiry reminders, weekly digest (opt-in), aur major product updates.

Help chahiye? Yahin reply karein. Har message ek insaan padhta hai.

— TradeTri team
`,

  required_vars: ["user_name"],
  cta: "Reply with any question",
  estimated_chars: 700,
  visuals_suggested: [
    "Optional: 1 product hero image (NO video, keeps WA file size down)",
    "Optional: 1 short voice note from Jayesh saying the same thing",
  ],
};
