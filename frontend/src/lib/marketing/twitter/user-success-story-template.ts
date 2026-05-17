import type { MarketingTemplate } from "../_types";

export const USER_SUCCESS_STORY_TEMPLATE: MarketingTemplate = {
  slug: "twitter-user-success-story-template",
  platform: "twitter",
  use_case: "Templated user success story tweet (with consent + honest framing)",
  audience: "general",

  content_en: `Real user, real numbers.

{{user_display_name}} — {{user_role_city}} — paper-traded {{strategy_name}} for {{tracking_days}} days.

Result: {{paper_pnl_pct}}% over {{trade_count}} trades. Max drawdown: {{max_dd_pct}}%.

What they did well: {{key_habit}}
What didn't go to plan: {{what_failed}}

We share both numbers. The losing trades are part of the story.

(Posted with user's permission. Past paper results don't predict live performance.)
`,
  content_hi: `Real user, real numbers.

{{user_display_name}} — {{user_role_city}} — {{strategy_name}} ko {{tracking_days}} din paper-trade kiya.

Result: {{paper_pnl_pct}}% over {{trade_count}} trades. Max drawdown: {{max_dd_pct}}%.

Kya sahi kiya: {{key_habit_hi}}
Kya plan ke according nahi gaya: {{what_failed_hi}}

Hum dono numbers share karte. Losing trades bhi story ka part hain.

(User ki permission se. Past paper results live performance predict nahi karte.)
`,

  required_vars: [
    "user_display_name",
    "user_role_city",
    "strategy_name",
    "tracking_days",
    "paper_pnl_pct",
    "trade_count",
    "max_dd_pct",
    "key_habit",
    "key_habit_hi",
    "what_failed",
    "what_failed_hi",
  ],
  cta: "Run this strategy yourself (paper, free): {{template_url}}",
  estimated_chars: 700,
  visuals_suggested: [
    "Anonymised equity curve from the user's actual paper account",
    "User photo IF they explicitly consented to face attribution",
    "Otherwise: silhouette + role/city tag",
  ],
};
