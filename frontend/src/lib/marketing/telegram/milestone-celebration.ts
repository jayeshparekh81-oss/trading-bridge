import type { MarketingTemplate } from "../_types";

export const MILESTONE_CELEBRATION: MarketingTemplate = {
  slug: "telegram-milestone-celebration",
  platform: "telegram",
  use_case: "Community milestone post (e.g. 1000 users, 1L paper trades, 100 days uptime)",
  audience: "general",

  content_en: `**Milestone: {{milestone_label}}** 🎉

{{milestone_one_liner}}

The numbers:
{{milestone_stats}}

What this means: {{interpretation}}

Honest reflection: {{honest_note}}

Thank you to every user who paper-traded, broke things, reported bugs, and told us what was missing. We built this for retail Indian traders who want systematic execution without paying a hedge fund.

Next milestone we're chasing: {{next_milestone}}
`,
  content_hi: `**Milestone: {{milestone_label}}** 🎉

{{milestone_one_liner_hi}}

Numbers:
{{milestone_stats_hi}}

Iska matlab: {{interpretation_hi}}

Honest reflection: {{honest_note_hi}}

Shukriya har user ka jisne paper-trade kiya, cheezein todin, bugs report ki, aur bataya kya missing tha. Hum ne ye retail Indian traders ke liye banaya jo systematic execution chahte hain hedge fund ka kharcha kiye bina.

Agla milestone: {{next_milestone_hi}}
`,

  required_vars: [
    "milestone_label",
    "milestone_one_liner",
    "milestone_one_liner_hi",
    "milestone_stats",
    "milestone_stats_hi",
    "interpretation",
    "interpretation_hi",
    "honest_note",
    "honest_note_hi",
    "next_milestone",
    "next_milestone_hi",
  ],
  cta: "Join the community at t.me/{{channel_handle}}",
  estimated_chars: 900,
  visuals_suggested: [
    "Number-card graphic with the milestone metric front and centre",
    "Photo of the founding team (if posting around a team-related milestone)",
    "Cricket-style scoreboard mock if hitting a count milestone",
  ],
};
