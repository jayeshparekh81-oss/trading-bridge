import type { MarketingTemplate } from "../_types";

export const STRATEGY_OF_WEEK: MarketingTemplate = {
  slug: "telegram-strategy-of-week",
  platform: "telegram",
  use_case: "Weekly featured strategy explainer (Wednesdays)",
  audience: "active_user",

  content_en: `**Strategy of the week: {{strategy_name}}** 🎯

What it does (one paragraph):
{{what_it_does}}

When it works:
{{best_conditions}}

When it doesn't:
{{worst_conditions}}

This week's paper results: {{week_pnl_pct}}% across {{user_count}} runs.

Common mistake to avoid: {{top_mistake}}

Difficulty: {{difficulty}}/5 | Capital efficiency: {{capital_efficiency}}/5

Clone the template (paper, free):
{{template_url}}

Full explainer with example trade and follow-up strategies: {{explainer_url}}
`,
  content_hi: `**Is hafte ki strategy: {{strategy_name}}** 🎯

Kya karta hai (ek paragraph):
{{what_it_does_hi}}

Kab kaam karta hai:
{{best_conditions_hi}}

Kab nahi karta:
{{worst_conditions_hi}}

Is hafte ka paper result: {{week_pnl_pct}}% across {{user_count}} runs.

Common galti: {{top_mistake_hi}}

Difficulty: {{difficulty}}/5 | Capital efficiency: {{capital_efficiency}}/5

Template clone karein (paper, free):
{{template_url}}

Pura explainer example trade aur follow-up strategies ke saath: {{explainer_url}}
`,

  required_vars: [
    "strategy_name",
    "what_it_does",
    "what_it_does_hi",
    "best_conditions",
    "best_conditions_hi",
    "worst_conditions",
    "worst_conditions_hi",
    "week_pnl_pct",
    "user_count",
    "top_mistake",
    "top_mistake_hi",
    "difficulty",
    "capital_efficiency",
    "template_url",
    "explainer_url",
  ],
  cta: "Clone the template at {{template_url}}",
  estimated_chars: 1000,
  visuals_suggested: [
    "Annotated daily chart showing one example trade entry/exit",
    "Strategy logic flowchart (2-3 boxes max)",
    "Difficulty/capital-efficiency radar chart",
  ],
};
