import type { EmailTemplate } from "./_types";

export const MONTHLY_NEWSLETTER: EmailTemplate = {
  slug: "monthly-newsletter",
  name: "Monthly product + market newsletter",
  category: "digest",

  subject_en: "TradeTri {{month_year}}: {{headline_strategy_name}} led the pack, {{new_feature_name}} shipped",
  subject_hi: "TradeTri {{month_year}}: {{headline_strategy_name}} top pe, {{new_feature_name}} ship hua",

  body_en: `Hi {{user_name}},

Welcome to the {{month_year}} TradeTri newsletter.

PRODUCT
{{product_updates}}

MARKETS THIS MONTH
{{market_recap}}

TOP STRATEGIES (paper, across all users)
1. {{top_1_name}}: {{top_1_pnl_pct}}% avg
2. {{top_2_name}}: {{top_2_pnl_pct}}% avg
3. {{top_3_name}}: {{top_3_pnl_pct}}% avg

Note: these are PAST RESULTS in a specific market. They don't predict next month's returns. The best strategy last month often isn't the best next month.

READING THIS MONTH
{{recommended_reading}}

NEXT MONTH'S OUTLOOK
{{forward_view}}

— Team TradeTri
{{unsubscribe_url}}
`,
  body_hi: `Namaste {{user_name}},

{{month_year}} TradeTri newsletter mein swagat hai.

PRODUCT
{{product_updates}}

IS MAHINE KE MARKETS
{{market_recap}}

TOP STRATEGIES (paper, sab users mein)
1. {{top_1_name}}: {{top_1_pnl_pct}}% avg
2. {{top_2_name}}: {{top_2_pnl_pct}}% avg
3. {{top_3_name}}: {{top_3_pnl_pct}}% avg

Note: ye PAST RESULTS specific market mein hain. Agle mahine ke returns predict nahi karte. Pichle mahine ki best strategy aksar next month ki best nahi hoti.

IS MAHINE KA READING
{{recommended_reading}}

AGLE MAHINE KA OUTLOOK
{{forward_view}}

— Team TradeTri
{{unsubscribe_url}}
`,

  required_vars: [
    "user_name",
    "month_year",
    "headline_strategy_name",
    "new_feature_name",
    "product_updates",
    "market_recap",
    "top_1_name",
    "top_1_pnl_pct",
    "top_2_name",
    "top_2_pnl_pct",
    "top_3_name",
    "top_3_pnl_pct",
    "recommended_reading",
    "forward_view",
    "unsubscribe_url",
  ],
};
