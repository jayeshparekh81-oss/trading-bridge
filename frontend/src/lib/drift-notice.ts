/**
 * Drift-notice copy — single source, same pattern as `risk-labels.ts`.
 *
 * ⚠️ TONE IS THE POINT. This banner appears because the customer closed a
 * position at their own broker. They did nothing wrong — it is their account
 * and their right. So the copy:
 *
 *   - states plainly what happened and what we did about it,
 *   - contains NO failure/error/problem wording (asserted by tests),
 *   - explicitly reassures ("Kuch galat nahi hua"),
 *   - and points at the existing Settings control to re-enable AUTO.
 *
 * Same discipline as the `subscriber_manual_action` notification copy: an event
 * that is working-as-designed must never be dressed up as a malfunction.
 */

export interface DriftNotice {
  /** ISO timestamp of the flip. */
  flipped_at: string;
  symbol: string | null;
  /** `broker_flat` = fully closed · `broker_partial` = part-closed. */
  reason: string;
}

export const DRIFT_NOTICE_TITLE =
  "Aapne yeh position apne broker par khud band ki thi";

/** Body copy. `symbol` is optional — the sentence reads correctly without it. */
export function driftNoticeBody(notice: DriftNotice): string {
  const what = notice.symbol ? `${notice.symbol} ` : "yeh position ";
  const how =
    notice.reason === "broker_partial"
      ? "poori tarah open nahi hai"
      : "ab open nahi hai";
  return (
    `TRADETRI ne dekha ki ${what}aapke broker par ${how}. ` +
    "Isliye is subscription ko MANUAL kar diya gaya — aage ke signals sirf " +
    "notification aayenge, koi order apne aap nahi lagega."
  );
}

/** The reassurance line. Rendered separately so it always stays visible. */
export const DRIFT_NOTICE_REASSURANCE =
  "Kuch galat nahi hua. Jab aap taiyaar ho, neeche Settings se AUTO wapas on kar sakte ho.";

/** Where the customer re-enables — the existing per-subscription control. */
export const DRIFT_NOTICE_CTA = "Neeche Settings mein mode badlo";
