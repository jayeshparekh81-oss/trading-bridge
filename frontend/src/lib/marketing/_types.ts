/**
 * Marketing content drafts — code-shaped templates for post-launch
 * distribution. CONTENT-ONLY: no posting infrastructure wired.
 * Drafts await founder review of tone, claims, and CTAs before any
 * channel send.
 *
 * Bilingual: every template has EN markdown + Hinglish "bhai-tone" HI.
 * Hinglish here means Roman-script Hindi mixed with English — NOT
 * Devanagari script and NOT corporate formal.
 */
export type Platform = "telegram" | "twitter" | "whatsapp" | "instagram";
export type Audience = "new_user" | "active_user" | "waitlist" | "general";

export interface MarketingTemplate {
  /** kebab-case identifier for registry lookups */
  slug: string;
  platform: Platform;
  use_case: string;
  audience: Audience;

  /** EN content as markdown. {{var_name}} for template variables */
  content_en: string;
  /** Hinglish bhai-tone, same {{var_name}} placeholders */
  content_hi: string;

  required_vars: string[];

  /** Primary call to action (one line) */
  cta: string;

  /** Approximate character count for platform-limit awareness */
  estimated_chars: number;

  /** Free-form notes on visuals (image, video, GIF) */
  visuals_suggested: string[];
}
