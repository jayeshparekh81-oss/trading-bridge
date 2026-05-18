/**
 * Email template content registry. Lookup by slug; null if not found.
 * Content-only — no send infrastructure here yet.
 */
import type { EmailTemplate } from "./_types";

import { WELCOME } from "./welcome";
import { FIRST_STRATEGY_NUDGE } from "./first-strategy-nudge";
import { WEEKLY_DIGEST } from "./weekly-digest";
import { PASSWORD_RESET } from "./password-reset";
import { TOKEN_EXPIRY_REMINDER } from "./token-expiry-reminder";
import { PAPER_MILESTONE } from "./paper-milestone";
import { BROKER_DISCONNECT_ALERT } from "./broker-disconnect-alert";
import { COMPLIANCE_UPDATE } from "./compliance-update";
import { MONTHLY_NEWSLETTER } from "./monthly-newsletter";
import { LIVE_TRADING_ANNOUNCEMENT } from "./live-trading-announcement";

export type { EmailTemplate } from "./_types";

const TEMPLATES_MAP: Record<string, EmailTemplate> = {
  welcome: WELCOME,
  "first-strategy-nudge": FIRST_STRATEGY_NUDGE,
  "weekly-digest": WEEKLY_DIGEST,
  "password-reset": PASSWORD_RESET,
  "token-expiry-reminder": TOKEN_EXPIRY_REMINDER,
  "paper-milestone": PAPER_MILESTONE,
  "broker-disconnect-alert": BROKER_DISCONNECT_ALERT,
  "compliance-update": COMPLIANCE_UPDATE,
  "monthly-newsletter": MONTHLY_NEWSLETTER,
  "live-trading-announcement": LIVE_TRADING_ANNOUNCEMENT,
};

export const TEMPLATES: Readonly<Record<string, EmailTemplate>> = TEMPLATES_MAP;
export const TEMPLATE_COUNT = Object.keys(TEMPLATES).length;

export function getTemplate(slug: string): EmailTemplate | null {
  return TEMPLATES[slug] ?? null;
}

export function listTemplates(): EmailTemplate[] {
  return Object.values(TEMPLATES);
}
