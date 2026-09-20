/**
 * Email template content registry. Lookup by slug; null if not found.
 * Content-only — no send infrastructure here yet.
 *
 * ⚠ NOTHING IN THIS FOLDER IS EVER SENT TODAY. Two measured reasons, 20 Sep 2026:
 *
 *   1. NO SENDER. The only importer of this registry in the whole repo is
 *      `tests/email/templates-registry.test.ts`. No page, no route and no server
 *      action renders or posts any of these. The backend's own mailer
 *      (`app/services/notification_service.py`) has a separate, much smaller set
 *      of event templates and never reads this folder.
 *   2. NO DELIVERY. AWS SES (ap-south-1) is in SANDBOX and the instance role may
 *      send only on ONE identity — the admin's own address. Proven in action the
 *      same day: the Sunday weekly-report task logged
 *      `weekly_report.complete users_notified=13` while 12 of 13 recipients got
 *      `AccessDenied … ses:SendEmail on … identity/<the customer's address>`.
 *
 * So these files are DRAFTS. They were still corrected on 20 Sep to stop
 * promising a reply-by-email that cannot happen, because a draft becomes a
 * promise the moment somebody wires a sender to it.
 *
 * BEFORE ANY OF THIS IS SENT TO A CUSTOMER, three things must be true — the list
 * lives in `ops/kb/PRE_LAUNCH_CHECKLIST.md`:
 *   (a) SES production access granted (out of sandbox),
 *   (b) the send policy widened past the single verified identity,
 *   (c) a real sending path, with unsubscribe handling for anything not
 *       transactional.
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
