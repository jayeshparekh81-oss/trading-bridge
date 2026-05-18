import type { MarketingTemplate } from "../_types";

export const COMPLIANCE_UPDATE: MarketingTemplate = {
  slug: "telegram-compliance-update",
  platform: "telegram",
  use_case: "SEBI/RBI rule change notice to channel members",
  audience: "general",

  content_en: `**Important: regulatory update** ⚖️

{{regulator}} has announced: {{change_headline}}

EFFECTIVE: {{effective_date}}

WHAT CHANGED (plain language):
{{change_plain_language}}

WHAT THIS MEANS FOR TRADETRI USERS:
{{tradetri_impact}}

WHAT WE'RE DOING:
{{tradetri_response}}

DO YOU NEED TO DO ANYTHING?
{{user_action_required}}

We will never blame regulators or complain about rules. Indian markets are well-regulated and we believe that's a feature, not a bug. If you have concerns, reply and our compliance lead Jayesh will respond personally.

Full notification: {{regulator_url}}
`,
  content_hi: `**Important: regulatory update** ⚖️

{{regulator}} ne announce kiya: {{change_headline_hi}}

EFFECTIVE: {{effective_date}}

KYA CHANGE HUA (plain language):
{{change_plain_language_hi}}

TRADETRI USERS PE ASAR:
{{tradetri_impact_hi}}

HUM KYA KAR RAHE HAIN:
{{tradetri_response_hi}}

AAP KO KUCH KARNA HAI?
{{user_action_required_hi}}

Hum kabhi regulators ko blame nahi karenge ya rules pe complain nahi karenge. Indian markets well-regulated hain aur hum maante hain ye feature hai, bug nahi. Concern ho to reply karein, hamare compliance lead Jayesh personally respond karenge.

Full notification: {{regulator_url}}
`,

  required_vars: [
    "regulator",
    "change_headline",
    "change_headline_hi",
    "effective_date",
    "change_plain_language",
    "change_plain_language_hi",
    "tradetri_impact",
    "tradetri_impact_hi",
    "tradetri_response",
    "tradetri_response_hi",
    "user_action_required",
    "user_action_required_hi",
    "regulator_url",
  ],
  cta: "Read full notification at {{regulator_url}}",
  estimated_chars: 1200,
  visuals_suggested: [
    "Official regulator logo (SEBI/RBI) + TradeTri logo split-screen",
    "Timeline graphic showing effective date and grace period",
  ],
};
