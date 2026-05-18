import type { EmailTemplate } from "./_types";

export const BROKER_DISCONNECT_ALERT: EmailTemplate = {
  slug: "broker-disconnect-alert",
  name: "Broker disconnected mid-session (auth failure or API outage)",
  category: "transactional",

  subject_en: "URGENT: {{broker_name}} disconnected — live strategies paused",
  subject_hi: "URGENT: {{broker_name}} disconnect ho gaya — live strategies paused",

  body_en: `Hi {{user_name}},

Your {{broker_name}} connection lost authorization at {{disconnect_time_ist}} IST. Reason: {{disconnect_reason}}.

WHAT WE'RE DOING
• All live strategies paused immediately.
• No new orders will be placed until you reauthorize.
• Existing open positions are untouched — those remain with your broker.

WHAT YOU SHOULD DO

1. Open {{reconnect_url}}
2. Sign in to your {{broker_name}} account
3. Approve permissions

If this disconnect was caused by your broker (e.g. their API was down), you don't need to do anything — we'll auto-reconnect once their service recovers. We'll send a confirmation email when that happens.

If you intended to disconnect, ignore this email.

For open positions you want to manage manually right now, use your broker's web/app interface — your account at {{broker_name}} is unaffected by this disconnect.

— Team TradeTri Ops
{{support_email}}
`,
  body_hi: `Namaste {{user_name}},

Aapka {{broker_name}} connection {{disconnect_time_ist}} IST pe authorization khote diya. Reason: {{disconnect_reason}}.

HUM KYA KAR RAHE HAIN
• Sab live strategies turant pause kar di.
• Reauthorize na karein tab tak naye orders place nahi honge.
• Existing open positions untouched — wo aapke broker ke saath hi hain.

AAP KO KYA KARNA CHAHIYE

1. {{reconnect_url}} open karein
2. Apne {{broker_name}} account mein sign in karein
3. Permissions approve karein

Agar ye disconnect aapke broker ke wajah se hua (e.g. unka API down tha) to aap ko kuch nahi karna — unki service recover hote hi hum auto-reconnect kar denge. Confirmation email bhejenge.

Aap ne khud disconnect intend kiya to is email ko ignore karein.

Open positions abhi manually manage karna ho to apne broker ke web/app interface use karein — {{broker_name}} pe aapka account is disconnect se unaffected hai.

— Team TradeTri Ops
{{support_email}}
`,

  required_vars: [
    "user_name",
    "broker_name",
    "disconnect_time_ist",
    "disconnect_reason",
    "reconnect_url",
    "support_email",
  ],
};
