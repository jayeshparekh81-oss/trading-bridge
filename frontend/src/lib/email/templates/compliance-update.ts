import type { EmailTemplate } from "./_types";

export const COMPLIANCE_UPDATE: EmailTemplate = {
  slug: "compliance-update",
  name: "SEBI/RBI compliance or regulatory update notice",
  category: "compliance",

  subject_en: "Important: regulatory update affecting your TradeTri use ({{regulator}})",
  subject_hi: "Important: aapke TradeTri use pe regulatory update ({{regulator}})",

  body_en: `Hi {{user_name}},

{{regulator}} has announced a regulatory change that affects how Indian retail traders interact with platforms like TradeTri. This email summarizes what changed, what we're doing, and what (if anything) you need to do.

WHAT CHANGED
{{change_summary}}

WHAT THIS MEANS FOR YOU
{{user_impact}}

WHAT WE'RE DOING
{{tradetri_response}}

EFFECTIVE DATE: {{effective_date}}

If you have questions, reply to this email — Jayesh (founder) reviews compliance questions personally. Compliance with Indian regulations is a hard line for us and we'd rather over-explain than have customers in violation.

Full details and the official notification are linked below:
{{regulator_url}}

— Team TradeTri Compliance
{{support_email}}
`,
  body_hi: `Namaste {{user_name}},

{{regulator}} ne ek regulatory change announce kiya jo Indian retail traders ke TradeTri jaise platforms ke saath interact karne ke tarike ko affect karta. Ye email summarize karta kya change hua, hum kya kar rahe, aur aap ko (agar kuch hai to) kya karna hai.

KYA CHANGE HUA
{{change_summary}}

ISKA AAP PE ASAR
{{user_impact}}

HUM KYA KAR RAHE HAIN
{{tradetri_response}}

EFFECTIVE DATE: {{effective_date}}

Sawaal hain to is email ka reply karein — Jayesh (founder) compliance questions personally review karte hain. Indian regulations ki compliance hamare liye hard line hai aur hum over-explain karna prefer karte customers ko violation mein dekhne ke compared.

Full details aur official notification neeche link hai:
{{regulator_url}}

— Team TradeTri Compliance
{{support_email}}
`,

  required_vars: [
    "user_name",
    "regulator",
    "change_summary",
    "user_impact",
    "tradetri_response",
    "effective_date",
    "regulator_url",
    "support_email",
  ],
};
