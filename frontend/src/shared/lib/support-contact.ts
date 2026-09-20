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

/** `mailto:` href for the support address, with an optional prefilled subject. */
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

export const SUPPORT_REPLY_PROMISE = SUPPORT_REPLY_PROMISE_INTERIM;
