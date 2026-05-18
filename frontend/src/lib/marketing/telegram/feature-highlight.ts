import type { MarketingTemplate } from "../_types";

export const FEATURE_HIGHLIGHT: MarketingTemplate = {
  slug: "telegram-feature-highlight",
  platform: "telegram",
  use_case: "Single-feature spotlight post (e.g. Strategy Tester, Glass Box, AlgoMitra)",
  audience: "general",

  content_en: `**Feature spotlight: {{feature_name}}** 🔍

{{feature_one_liner}}

Why this matters for Indian traders:
{{feature_why_indian_context}}

How to use it (takes < 2 min):
1. {{step_1}}
2. {{step_2}}
3. {{step_3}}

Real example from our paper users:
{{user_paper_example}}

Try it: {{feature_url}}

We're rolling out one feature spotlight per week. Reply with what you'd like to see covered next.
`,
  content_hi: `**Feature spotlight: {{feature_name}}** 🔍

{{feature_one_liner_hi}}

Indian traders ke liye kyu zaroori hai:
{{feature_why_indian_context_hi}}

Kaise use karein (< 2 min):
1. {{step_1_hi}}
2. {{step_2_hi}}
3. {{step_3_hi}}

Hamare paper users ka real example:
{{user_paper_example_hi}}

Try karein: {{feature_url}}

Hum har hafte ek feature spotlight roll-out karte hain. Aage kya cover karein, reply mein batao.
`,

  required_vars: [
    "feature_name",
    "feature_one_liner",
    "feature_one_liner_hi",
    "feature_why_indian_context",
    "feature_why_indian_context_hi",
    "step_1",
    "step_2",
    "step_3",
    "step_1_hi",
    "step_2_hi",
    "step_3_hi",
    "user_paper_example",
    "user_paper_example_hi",
    "feature_url",
  ],
  cta: "Try {{feature_name}} at {{feature_url}}",
  estimated_chars: 1100,
  visuals_suggested: [
    "Annotated screenshot of the feature in product",
    "30-sec screen recording showing 3-step usage",
    "Before/after comparison if applicable (e.g., manual vs auto)",
  ],
};
