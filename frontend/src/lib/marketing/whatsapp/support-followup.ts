import type { MarketingTemplate } from "../_types";

export const SUPPORT_FOLLOWUP: MarketingTemplate = {
  slug: "whatsapp-support-followup",
  platform: "whatsapp",
  use_case: "Support ticket follow-up message (resolution check)",
  audience: "active_user",

  content_en: `Hi {{user_name}},

Following up on your ticket from {{ticket_date}} — "{{ticket_summary}}".

We marked it resolved on {{resolved_date}}. Did the fix actually work for you?

Reply with:
👍 Yes, it's working
👎 No, still seeing it
🤔 Different issue now

If the issue isn't fully fixed, we'd rather know — we don't measure closed-ticket count, we measure problems-actually-solved.

— TradeTri support
`,
  content_hi: `Namaste {{user_name}},

{{ticket_date}} wala ticket follow-up — "{{ticket_summary}}".

Hum ne {{resolved_date}} ko resolved mark kiya. Fix actually kaam kar raha?

Reply karein:
👍 Haan, kaam kar raha
👎 Nahi, abhi bhi ho raha
🤔 Ab different issue aa raha

Issue fully fixed nahi to hamein bata dein — hum closed-ticket count nahi measure karte, problems-actually-solved measure karte.

— TradeTri support
`,

  required_vars: ["user_name", "ticket_date", "ticket_summary", "resolved_date"],
  cta: "Reply with status",
  estimated_chars: 600,
  visuals_suggested: ["Plain text only"],
};
