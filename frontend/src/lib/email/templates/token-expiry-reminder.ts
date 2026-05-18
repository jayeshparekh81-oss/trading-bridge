import type { EmailTemplate } from "./_types";

export const TOKEN_EXPIRY_REMINDER: EmailTemplate = {
  slug: "token-expiry-reminder",
  name: "Broker session/token expiry reminder (T-12h)",
  category: "transactional",

  subject_en: "Your {{broker_name}} session expires in {{hours_remaining}} hours",
  subject_hi: "Aapki {{broker_name}} session {{hours_remaining}} ghante mein expire hogi",

  body_en: `Hi {{user_name}},

Heads up: your {{broker_name}} session token expires at {{expiry_time_ist}} IST ({{hours_remaining}} hours from now).

Indian broker APIs require daily session reauthorization for security. Without an active token, your live strategies will pause and no new orders will be placed.

To reauthorize:
1. Open {{login_url}}
2. Sign in to your broker account
3. Approve TradeTri's read+order permissions

This takes 30 seconds. Your existing positions and orders are unaffected — only NEW orders pause until you reauthorize.

If you'd prefer SMS reminders instead of email, change preference in Settings → Notifications.

— Team TradeTri
`,
  body_hi: `Namaste {{user_name}},

Heads up: aapki {{broker_name}} session token {{expiry_time_ist}} IST pe expire hogi ({{hours_remaining}} ghante mein).

Indian broker APIs security ke liye daily session reauthorization require karte. Active token ke bina, aapki live strategies pause ho jaayengi aur naye orders place nahi honge.

Reauthorize karne ke liye:
1. {{login_url}} open karein
2. Apne broker account mein sign in karein
3. TradeTri ki read+order permissions approve karein

30 second lagte hain. Existing positions aur orders unaffected rahenge — sirf NAYE orders pause jab tak reauthorize na karein.

SMS reminders prefer karein email ke jagah to Settings → Notifications mein preference change karein.

— Team TradeTri
`,

  required_vars: [
    "user_name",
    "broker_name",
    "expiry_time_ist",
    "hours_remaining",
    "login_url",
  ],
};
