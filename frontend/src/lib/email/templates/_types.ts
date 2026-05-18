/**
 * Email template content shape — used by all welcome/transactional/digest
 * templates. Each template provides EN + Hinglish (HI) variants for both
 * subject and body. `required_vars` lists the template variable names
 * (e.g. "user_name", "broker_name") that the renderer must substitute
 * before sending; tests use it to validate that no template references
 * a variable it didn't declare.
 *
 * NOTE: This is CONTENT-ONLY. There is no email infrastructure wired in
 * yet — these files exist for founder review and future plumbing.
 */
export interface EmailTemplate {
  /** kebab-case file slug for registry lookups */
  slug: string;

  /** human-readable label shown in admin UI */
  name: string;

  /** transactional | digest | welcome | nudge | compliance */
  category: "transactional" | "digest" | "welcome" | "nudge" | "compliance";

  subject_en: string;
  subject_hi: string;

  /** plain-text body. Variables are referenced as {{var_name}} */
  body_en: string;
  body_hi: string;

  /** ordered list of variable names this template uses (without braces) */
  required_vars: string[];
}
