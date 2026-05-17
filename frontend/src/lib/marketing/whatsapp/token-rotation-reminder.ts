import type { MarketingTemplate } from "../_types";

export const TOKEN_ROTATION_REMINDER: MarketingTemplate = {
  slug: "whatsapp-token-rotation-reminder",
  platform: "whatsapp",
  use_case: "Daily broker session token rotation reminder (sent T-2h before expiry)",
  audience: "active_user",

  content_en: `{{user_name}}, your {{broker_name}} session expires in {{hours_remaining}} hours ({{expiry_time_ist}} IST).

Without rotation, your live strategies will pause. Existing positions stay safe with your broker.

Rotate now (30 seconds): {{rotate_url}}

— TradeTri
`,
  content_hi: `{{user_name}}, aapki {{broker_name}} session {{hours_remaining}} ghante mein expire hogi ({{expiry_time_ist}} IST).

Rotate nahi kiya to live strategies pause ho jaayengi. Existing positions safe rahenge broker ke paas.

Abhi rotate karein (30 second): {{rotate_url}}

— TradeTri
`,

  required_vars: [
    "user_name",
    "broker_name",
    "hours_remaining",
    "expiry_time_ist",
    "rotate_url",
  ],
  cta: "Rotate at {{rotate_url}}",
  estimated_chars: 350,
  visuals_suggested: [
    "Minimal: no image needed. WhatsApp transactional templates work best as plain text.",
  ],
};
