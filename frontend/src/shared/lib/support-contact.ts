/**
 * The ONE place the customer-facing support address is defined.
 *
 * Founder decision, 20 Sep 2026, NOT negotiable: every customer-facing page shows
 * `support@tradetri.com`. His personal Gmail must not appear anywhere a customer can
 * see it, and the old `support@tradetri.in` variant is gone.
 *
 * Before this file there were THREE different answers on the live site:
 *   - `frontend/src/components/legal/legal-page.tsx`      his personal Gmail
 *   - `frontend/src/app/(public)/contact/page.tsx`        his personal Gmail
 *   - `frontend/src/lib/algomitra-personality.ts`         support@tradetri.in
 *   - `frontend/src/lib/help/faq-content.ts`              support@tradetri.com
 * That is a one-source-per-fact violation and it was customer-visible. Anything that
 * needs the support address imports it from here. `shared` is the bottom FSD layer
 * (ADR 0001 §1), so app / widgets / features / entities / legacy may all import it.
 *
 * The backend agrees: `SUPPORT_EMAIL_TO` defaults to the same address
 * (`backend/app/strategy_engine/api/support.py`).
 */
export const SUPPORT_EMAIL = "support@tradetri.com";

/**
 * `mailto:` href for the support address, with an optional prefilled subject.
 *
 * ⚠ **DO NOT USE IT YET — it has zero callers on purpose (20 Sep 2026).** Every customer-facing
 * `mailto:` was removed because `support@tradetri.com` receives nothing (no MX record). Kept so the
 * link can be restored in one place the day forwarding exists (PRE_LAUNCH_CHECKLIST §0.2). Wiring it
 * back before then turns the guard test `tests/copy/no-unkeepable-contact-promise.test.ts` red, which
 * is exactly what should happen.
 */
export function supportMailto(subject?: string, body?: string): string {
  const params: string[] = [];
  if (subject) params.push(`subject=${encodeURIComponent(subject)}`);
  if (body) params.push(`body=${encodeURIComponent(body)}`);
  return `mailto:${SUPPORT_EMAIL}${params.length ? `?${params.join("&")}` : ""}`;
}

/**
 * WHAT WE PROMISE A CUSTOMER ABOUT SUPPORT RESPONSE — one source, one flip.
 *
 * Founder, 20 Sep 2026: *"never promise what we don't do"*, and
 * *"if that can't be done today, change the wording until it can."*
 *
 * THE FACTS, measured the same day:
 *   - A new support ticket used to notify NOBODY. `_notify_admin_stub` wrote a
 *     log line and stopped. `support_tickets` was at 0 rows, so nobody had been
 *     burned yet — the FIRST ticket ever filed would have sat unseen.
 *   - The routing that fixes it is BACKEND code. It is written and landed, but a
 *     landed backend change does nothing until the next image rebuild + container
 *     restart, and that restart needs the founder's haan under RULES #21/#26.
 *   - So between the publish of this wording and that restart, a "human reply in
 *     24-48 hours" would still be false. Hence the interim text below.
 *   - `support@tradetri.com` also does not RECEIVE mail yet: tradetri.com has NO
 *     MX record (measured 20 Sep 2026), so the email route is not promised either.
 *
 * ── HOW TO RESTORE THE STRONG WORDING (one edit, not a memory) ──
 * On the day the backend restart lands and the first ticket Telegram is seen:
 *   set SUPPORT_REPLY_PROMISE = SUPPORT_REPLY_PROMISE_AFTER_ROUTING
 * and publish. Nothing else changes. This step is also written into
 * `ops/kb/HANDOFF.md` and the backend-restart runbook, so it is on a checklist
 * rather than in somebody's head.
 */
export const SUPPORT_REPLY_PROMISE_AFTER_ROUTING = {
  en: "a human reply in 24-48 hours, with priority routing for billing / broker connection / critical bugs",
  hi: "24-48 ghante mein human reply, billing / broker connection / critical bugs ke liye priority routing",
} as const;

/** INTERIM — true today. Says what happens, and promises no clock we cannot keep. */
export const SUPPORT_REPLY_PROMISE_INTERIM = {
  en: "every ticket is recorded and read, and billing / broker-connection / critical bugs are picked up first — we are not putting a reply time in writing until we can keep it",
  hi: "har ticket record hota hai aur padha jata hai, aur billing / broker-connection / critical bugs pehle uthaye jate hain — jab tak hum time nibha na sake, tab tak koi reply time likh kar nahi de rahe",
} as const;

/**
 * 🔒 IS THE TICKET -> TELEGRAM ROUTING ACTUALLY LIVE?  Measured: NO.
 *
 * Founder, 2026-09-21, verbatim: *"The honest wording stays until the ticket->Telegram path
 * is actually live after a restart — don't let anyone remove it early."*
 *
 * This flag exists because the guard below used to be tied to the EMAIL flags, and that was
 * right only by accident. Ticket routing and email are THREE different facts, not one:
 *   - can a customer's mail reach us?            SUPPORT_EMAIL_RECEIVES
 *   - can we send mail to a customer?            SUPPORT_EMAIL_CAN_SEND_TO_CUSTOMERS
 *   - does a filed ticket reach a human at all?  ** this flag **
 * The day support@ forwarding is set up, the first two flip to true. If the promise were
 * gated only on those, the strong "24-48 hours" wording would unlock on that day even though
 * the backend restart that makes a ticket reach anyone had never happened. That is precisely
 * the early removal he forbade, and it would have been a reasonable-looking edit.
 *
 * WHAT EARNS THE FLIP — all three, in order, no shortcuts:
 *   1. the backend rebuild + restart lands (RULES #21 gate, his haan) — kb/RESTART_CHECKLIST.md 1.1;
 *   2. a REAL ticket is filed and its Telegram is SEEN on his phone. Landed code is not a live
 *      channel; `get_settings()` is lru_cached, so until the restart the routing does nothing;
 *   3. only then set this to true AND set SUPPORT_REPLY_PROMISE = SUPPORT_REPLY_PROMISE_AFTER_ROUTING.
 *
 * Until step 2 has actually been observed, this stays false. Changing it without the receipt
 * is the one thing this constant is here to make loud.
 */
export const SUPPORT_TICKET_ROUTING_LIVE = false;

/**
 * The promise that actually ships.
 *
 * It is NOT a free choice: `tests/copy/no-unkeepable-contact-promise.test.ts` derives the
 * expected value from SUPPORT_TICKET_ROUTING_LIVE, so flipping this line alone turns the
 * build red, and flipping the flag alone turns it red too. They move together or not at all.
 */
export const SUPPORT_REPLY_PROMISE = SUPPORT_TICKET_ROUTING_LIVE
  ? SUPPORT_REPLY_PROMISE_AFTER_ROUTING
  : SUPPORT_REPLY_PROMISE_INTERIM;

/* ───────────────────────────────────────────────────────────────────────────
 * CAN EMAIL ACTUALLY CARRY A MESSAGE TODAY? Two directions, both measured.
 *
 * Founder decision, 20 Sep 2026 (SETTLED, REQUIREMENTS §13): support email
 * forwarding is SKIPPED until paying customers arrive. Until then **no
 * customer-facing surface may promise an email reply, an email notification
 * or a response time we cannot deliver.**
 *
 * INBOUND — a customer writing TO us:  NO.
 *   `dig MX tradetri.com` → empty. No SPF/TXT, no DMARC. NS = dns-parking.com
 *   (Hostinger, parked). `tradetri.in` has no MX either. Mail addressed to
 *   support@tradetri.com goes nowhere; the sender gets a bounce or silence.
 *
 * OUTBOUND — us writing TO a customer:  NO.
 *   AWS SES (ap-south-1) is in SANDBOX and the instance role may send only on
 *   ONE identity — the founder's own address. Proven IN ACTION, not argued:
 *   the Sunday 18:00 IST weekly-report task ran 2026-09-20 12:30 UTC and
 *   logged `weekly_report.complete users_notified=13` with 12 of 13 recipients
 *   failing three attempts each:
 *     AccessDenied … not authorized to perform 'ses:SendEmail' on resource
 *     arn:aws:ses:ap-south-1:…:identity/<the customer's own address>
 *   Exactly one recipient — the admin — got `email: "sent"`.
 *
 * So BOTH directions are dead for a customer right now. Anything that reads
 * "email us" / "we'll email you" / "reply to this email" is a promise the
 * product cannot keep, and the guard test
 * `tests/copy/no-unkeepable-contact-promise.test.ts` fails the build if one
 * comes back while these two flags are false.
 *
 * WHEN THEY FLIP (each is one line here, plus the checklist step that earns it):
 *   INBOUND  ← `support@tradetri.com` forwarding set up in Hostinger hPanel
 *              (Emails → Email Forwarders; no nameserver change) —
 *              `ops/kb/PRE_LAUNCH_CHECKLIST.md` item 1.
 *   OUTBOUND ← SES production access granted AND the send policy widened past
 *              the single verified identity — PRE_LAUNCH_CHECKLIST item 2.
 * ─────────────────────────────────────────────────────────────────────────── */

/** Can a message a customer sends to SUPPORT_EMAIL reach us today? Measured: no. */
export const SUPPORT_EMAIL_RECEIVES = false;

/** Can we deliver mail to a customer's address today? Measured: no. */
export const SUPPORT_EMAIL_CAN_SEND_TO_CUSTOMERS = false;

/** The in-app support ticket — the one written channel that works today. */
export const SUPPORT_TICKET_PATH = "/help#ticket";

/** WhatsApp — the one channel a LOGGED-OUT visitor can actually use. */
export const SUPPORT_WHATSAPP_NUMBER = "919909031286";

/** `https://wa.me/…` link, optionally carrying the visitor's own message. */
export function supportWhatsapp(text?: string): string {
  const msg = text?.trim() ? text : "Hi, I have a question about TRADETRI";
  return `https://wa.me/${SUPPORT_WHATSAPP_NUMBER}?text=${encodeURIComponent(msg)}`;
}

/**
 * ONE next step per surface (RULES #40: one clear next step, plain language).
 *   PUBLIC  = a visitor who is not logged in → WhatsApp, because the ticket
 *             form needs an account (`create_ticket` requires an authenticated
 *             user, `backend/app/strategy_engine/api/support.py:302`).
 *   IN_APP  = a signed-in customer → the ticket, because it is recorded, read
 *             and (after the next backend restart) alerts a human.
 */
export const SUPPORT_ROUTE_PUBLIC = {
  en: "The quickest way to reach us is WhatsApp — our email is not receiving mail yet.",
  hi: "Humse baat karne ka sabse tez rasta WhatsApp hai — email abhi receive nahi kar rahi.",
} as const;

export const SUPPORT_ROUTE_IN_APP = {
  en: "Send a ticket from Help — it is recorded and read. WhatsApp works too.",
  hi: "Help se ticket bhejo — woh record hota hai aur padha jata hai. WhatsApp bhi chalta hai.",
} as const;
