/**
 * NO CUSTOMER-FACING SURFACE MAY PROMISE AN EMAIL WE CANNOT DELIVER.
 *
 * Founder decision, 20 Sep 2026 (SETTLED, REQUIREMENTS §13): support email
 * forwarding is skipped until paying customers arrive, and until then the
 * honest wording stays — "no customer-facing page may promise an email reply
 * we cannot deliver".
 *
 * WHY THIS FILE EXISTS. Both directions of email were dead and the site said
 * otherwise in eleven places at once. Measured that day:
 *
 *   INBOUND  `dig MX tradetri.com` → EMPTY. No SPF, no DMARC, NS = parked.
 *            Anything a customer sent to support@tradetri.com vanished.
 *   OUTBOUND AWS SES (ap-south-1) in SANDBOX, send policy limited to ONE
 *            identity. The Sunday 18:00 IST weekly-report task ran at
 *            2026-09-20 12:30 UTC and logged
 *            `weekly_report.complete users_notified=13` — with 12 of the 13
 *            failing three attempts each on
 *            `AccessDenied … ses:SendEmail … identity/<customer address>`.
 *            Exactly one recipient (the admin) got `email: "sent"`.
 *
 * The phrases below are the ones that were ACTUALLY LIVE, in both languages we
 * ship. Enumerating English only is how a bilingual product keeps its lie
 * (the lesson of `no-white-box-claim.test.ts`).
 *
 * TWO THINGS THIS TEST DELIBERATELY DOES **NOT** FLAG:
 *   · `shared/lib/support-contact.ts` — it holds the FUTURE wording
 *     (`SUPPORT_REPLY_PROMISE_AFTER_ROUTING`) on purpose, so the strong promise
 *     can be restored with one edit the day it becomes true. It is asserted
 *     directly in section 2 instead.
 *   · "24-48 ghante screen se door" in `algomitra-flows.ts` — that is advice to
 *     take a break from screens after a losing streak, not an email promise.
 *     Section 3 proves the vocabulary does not fire on it.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, sep } from "node:path";

import {
  SUPPORT_EMAIL_RECEIVES,
  SUPPORT_EMAIL_CAN_SEND_TO_CUSTOMERS,
  SUPPORT_REPLY_PROMISE,
  SUPPORT_REPLY_PROMISE_INTERIM,
  SUPPORT_REPLY_PROMISE_AFTER_ROUTING,
  SUPPORT_TICKET_PATH,
  supportWhatsapp,
} from "@/shared/lib/support-contact";

const SRC = join(process.cwd(), "src");

/** The one file allowed to carry the future wording — asserted separately. */
const PROMISE_SOURCE = "shared/lib/support-contact.ts";

/** INBOUND — "write to us by email", when nothing addressed to us is received. */
export const INBOUND_EMAIL_PROMISE: readonly RegExp[] = [
  /email us\b/i,                       // en — the contact page's own button
  /opens your email app/i,             // en — the helper text under it
  /reply to this email/i,              // en — welcome + compliance templates
  /is email ka reply/i,                // hinglish — the same two templates
  /email (karo|kar de|kar dein)\b/i,   // hinglish — "send us a mail"
];

/** OUTBOUND — "we will email you", when no customer address can be delivered to. */
export const OUTBOUND_EMAIL_PROMISE: readonly RegExp[] = [
  /we'?ll email you/i,                 // en — the notify-me dialog
  /we will email you/i,                // en
  /email you when/i,                   // en
  /email (karenge|bhejenge)/i,         // hinglish — suspension warning, broker alert
  /confirmation email/i,               // en/hinglish
  /email par jawab/i,                  // hinglish — the help page's ticket line
];

/** A CLOCK we cannot keep, and auth routes that do not exist. */
export const UNKEEPABLE_ROUTE_OR_CLOCK: readonly RegExp[] = [
  /respond within \d+ ?hours?/i,       // en — the welcome template's 24h
  /resolve within \d+ ?h\b/i,          // en — the login FAQ
  /\d+ ghante mein (response|resolve)/i, // hinglish — the same two
  /forgot[\s-]?password/i,             // en/hinglish — no such link or route exists
  /otp email/i,                        // en/hinglish — no email verification exists
];

const ALL = [
  ...INBOUND_EMAIL_PROMISE,
  ...OUTBOUND_EMAIL_PROMISE,
  ...UNKEEPABLE_ROUTE_OR_CLOCK,
];

function walk(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|mdx?)$/.test(e)) out.push(p);
  }
  return out;
}

/** Strip comments — prose ABOUT the rule is not a violation of it. */
function code(path: string): string {
  return readFileSync(path, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "");
}

const rel = (p: string) => p.replace(SRC + sep, "src" + sep);
const SHIPPED = walk(SRC).filter(
  (p) => !p.endsWith(PROMISE_SOURCE.replace(/\//g, sep)),
);

// ═══════════════════════════════════════════════════════════════════════
// 1. 🔴 No shipped file promises a mail in either direction
// ═══════════════════════════════════════════════════════════════════════

describe("no inbound 'email us' promise while nothing is received", () => {
  it.each(INBOUND_EMAIL_PROMISE)("no file matches %s", (re) => {
    expect(SHIPPED.filter((p) => re.test(code(p))).map(rel)).toEqual([]);
  });
});

describe("no outbound 'we'll email you' promise while nothing can be sent", () => {
  it.each(OUTBOUND_EMAIL_PROMISE)("no file matches %s", (re) => {
    expect(SHIPPED.filter((p) => re.test(code(p))).map(rel)).toEqual([]);
  });
});

describe("no reply clock, and no auth route that does not exist", () => {
  it.each(UNKEEPABLE_ROUTE_OR_CLOCK)("no file matches %s", (re) => {
    expect(SHIPPED.filter((p) => re.test(code(p))).map(rel)).toEqual([]);
  });
});

it("no shipped file opens a mail app (mailto:)", () => {
  expect(SHIPPED.filter((p) => /mailto:/i.test(code(p))).map(rel)).toEqual([]);
});

// ═══════════════════════════════════════════════════════════════════════
// 2. 🔴 The promise cannot be upgraded while the channels are dead
// ═══════════════════════════════════════════════════════════════════════

describe("the reply promise matches what the channels can do", () => {
  it("both directions are still measured as dead", () => {
    expect(SUPPORT_EMAIL_RECEIVES).toBe(false);
    expect(SUPPORT_EMAIL_CAN_SEND_TO_CUSTOMERS).toBe(false);
  });

  it("while they are dead, the interim promise is the one that ships", () => {
    expect(SUPPORT_REPLY_PROMISE).toBe(SUPPORT_REPLY_PROMISE_INTERIM);
    expect(SUPPORT_REPLY_PROMISE.en).not.toMatch(/24-48/);
    expect(SUPPORT_REPLY_PROMISE.hi).not.toMatch(/24-48/);
  });

  it("the stronger wording survives, so restoring it stays a one-line edit", () => {
    expect(SUPPORT_REPLY_PROMISE_AFTER_ROUTING.en).toMatch(/24-48 hours/);
    expect(SUPPORT_REPLY_PROMISE_AFTER_ROUTING.hi).toMatch(/24-48 ghante/);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 3. 🔴 The guard catches what was live, and spares what was innocent
// ═══════════════════════════════════════════════════════════════════════

describe("the vocabulary catches the exact strings that shipped on 20 Sep 2026", () => {
  const hits = (text: string) => ALL.some((re) => re.test(text));

  it("catches the contact page's own button and helper", () => {
    expect(hits("Email Us")).toBe(true);
    expect(hits("Opens your email app addressed to support@tradetri.com.")).toBe(true);
  });

  it("catches the welcome template, both languages", () => {
    expect(hits("If you get stuck, reply to this email and a human will respond within 24 hours.")).toBe(true);
    expect(hits("Stuck ho jaayein to is email ka reply kar dein, ek insaan 24 hours mein response dega.")).toBe(true);
  });

  it("catches the notify-me dialog", () => {
    expect(hits("We'll email you when Midnight launches!")).toBe(true);
    expect(hits("We'll email you when Midnight is available.")).toBe(true);
  });

  it("catches the help page's ticket line and the suspension warning", () => {
    expect(hits("Ticket bhejo — hum email par jawab denge.")).toBe(true);
    expect(hits("hum hamesha pehle email karenge unless violation active hai")).toBe(true);
  });

  it("catches the two auth dead ends a locked-out customer was sent down", () => {
    expect(hits("Login page → 'Forgot Password' link → email enter kar.")).toBe(true);
    expect(hits("email not verified yet — check inbox for the OTP email")).toBe(true);
  });

  it("does NOT fire on the screen-break advice, which is not about email", () => {
    expect(hits("• 24-48 ghante screen se door")).toBe(false);
  });

  it("does NOT fire on the honest replacements now shipping", () => {
    expect(hits("Send on WhatsApp")).toBe(false);
    expect(hits("Opens WhatsApp with your message already typed. We read it there.")).toBe(false);
    expect(hits("har ticket record hota hai aur padha jata hai")).toBe(false);
    expect(hits("Saved — Midnight will show up here the day it is ready.")).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 4. The routes that DO work are actually on the page
// ═══════════════════════════════════════════════════════════════════════

describe("every surface that lost an email route gained a working one", () => {
  it("the public contact page sends through WhatsApp and offers the ticket", () => {
    const page = code(join(SRC, "app/(public)/contact/page.tsx"));
    expect(page).toMatch(/supportWhatsapp\(/);
    expect(page).toMatch(/Send on WhatsApp/);
    expect(page).toContain(SUPPORT_TICKET_PATH);
  });

  it("the shared legal shell (terms/privacy/disclaimer/sebi) points at WhatsApp", () => {
    const legal = code(join(SRC, "components/legal/legal-page.tsx"));
    expect(legal).toMatch(/supportWhatsapp\(/);
    expect(legal).toMatch(/WhatsApp/);
  });

  it("the privacy page names a data-request route that works", () => {
    const privacy = code(join(SRC, "app/(public)/privacy/page.tsx"));
    expect(privacy).toMatch(/WhatsApp/);
    expect(privacy).toMatch(/ticket from Help/);
  });

  it("AlgoMitra escalates to the ticket, not to a mail app", () => {
    const quick = code(join(SRC, "components/algomitra/QuickActions.tsx"));
    expect(quick).toMatch(/ticketUrl/);
    expect(quick).not.toMatch(/emailUrl/);
  });

  it("the WhatsApp helper builds a real wa.me link and carries the message", () => {
    expect(supportWhatsapp()).toMatch(/^https:\/\/wa\.me\/\d+\?text=/);
    expect(supportWhatsapp("stop my strategy")).toContain(encodeURIComponent("stop my strategy"));
  });
});

// ═══════════════════════════════════════════════════════════════════════
// 5. The vocabulary must not quietly shrink
// ═══════════════════════════════════════════════════════════════════════

it("the guard stays bilingual and cannot be narrowed to English", () => {
  expect(INBOUND_EMAIL_PROMISE.length).toBeGreaterThanOrEqual(5);
  expect(OUTBOUND_EMAIL_PROMISE.length).toBeGreaterThanOrEqual(6);
  expect(UNKEEPABLE_ROUTE_OR_CLOCK.length).toBeGreaterThanOrEqual(5);
  const self = readFileSync(
    join(process.cwd(), "tests/copy/no-unkeepable-contact-promise.test.ts"),
    "utf8",
  );
  for (const hinglish of ["is email ka reply", "email par jawab", "ghante mein"]) {
    expect(self).toContain(hinglish);
  }
});
