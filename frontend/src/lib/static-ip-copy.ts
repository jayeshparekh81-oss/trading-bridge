/**
 * Static-IP onboarding copy (Rasta A, master D3) — the rules a customer must
 * read BEFORE they whitelist, in plain Hinglish, so nobody locks themselves out.
 *
 * The RULES (measured, kb/customer/STATIC_IP_COST.md, 24 Sep 2026):
 *   - Dhan allows ONE static IP per PERSON (no sharing, no pooling).
 *   - After whitelisting, that IP is LOCKED for 7 days — it cannot be changed.
 *   - Cost ≈ ₹350 per customer per month before GST (GST line NOT MEASURED —
 *     read from the invoice, never assumed here).
 *
 * These are the SAME rules `backend/app/domains/customer_lane/ip_lock.py`
 * enforces in code (7-day broker lock + the once-per-calendar-week clock,
 * fails closed). Copy and code must agree — the test pins the numbers to the
 * constants below so a change in one place fails until the other follows.
 *
 * NOT a source of the IP itself, the lock date, or the cost figure shown to a
 * customer: those come from the backend when the lane is on.
 */

export const DHAN_IP_LOCK_DAYS = 7;
export const DHAN_IPS_PER_PERSON = 1;
/** ₹/customer/month BEFORE GST — a measured figure with its basis, never a promise. */
export const STATIC_IP_COST_INR_BEFORE_GST = 350;
export const STATIC_IP_COST_BASIS =
  "AWS public IPv4 $0.005/h × 730 h × ₹95.96/$ ≈ ₹350/month before GST (kb/customer/STATIC_IP_COST.md, 24 Sep 2026); GST NOT MEASURED";

/** Shown ABOVE the whitelist step. Every line says what to DO, not what fails. */
export const STATIC_IP_RULES_HI: readonly string[] = [
  `Dhan ek insaan ke liye sirf ${DHAN_IPS_PER_PERSON} static IP allow karta hai — yeh IP sirf aapka hoga, kisi ke saath share nahi.`,
  `Ek baar whitelist hone ke baad yeh IP ${DHAN_IP_LOCK_DAYS} din tak badla NAHI ja sakta. Isliye pehle confirm karo ki yahi IP chahiye.`,
  `Galat IP whitelist hua to ${DHAN_IP_LOCK_DAYS} din tak orders nahi jaenge — aur hum use unlock nahi kar sakte, Dhan bhi nahi.`,
  `Kharcha: lagbhag ₹${STATIC_IP_COST_INR_BEFORE_GST} per mahina (GST alag; exact rakam invoice se).`,
];

/** The one next step under the rules. */
export const STATIC_IP_NEXT_STEP_HI =
  "Agla kadam: 'IP whitelist karo' dabao — hum aapke Dhan account me yahi ek IP register karenge.";

/** When the lock refuses a change: WHEN it opens, never just "no". */
export function ipLockRefusalLine(allowedFromIso: string | null): string {
  if (!allowedFromIso) return "IP abhi badla nahi ja sakta; kab khulega yeh pata nahi (NOT MEASURED).";
  const d = new Date(allowedFromIso);
  if (Number.isNaN(d.getTime())) return "IP abhi badla nahi ja sakta; kab khulega yeh pata nahi (NOT MEASURED).";
  const ist = d.toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  return `IP abhi badla nahi ja sakta — ${DHAN_IP_LOCK_DAYS} din ka lock hai. Agla mauka: ${ist} IST.`;
}
