/**
 * NSE market-hours utility.
 *
 * The Indian equity cash market (NSE) runs Monday–Friday from
 * 09:15 to 15:30 IST. Outside that window the chart WS feed has
 * no live ticks to push, so we use this helper to gate the
 * "Reconnecting…" badge — when the market is closed, retrying
 * forever is pointless churn and the user shouldn't see a
 * reconnect-spam banner.
 *
 * Timezone discipline
 *   The check is anchored in **Asia/Kolkata** explicitly via
 *   ``Intl.DateTimeFormat`` so that:
 *     - Users in any timezone (US, EU, SG) see the correct
 *       India-business-day window.
 *     - DST in the user's local zone never affects the answer.
 *       (India does not observe DST, so the IST offset is a
 *       constant +05:30 — but ``Intl`` is still the safest
 *       primitive to avoid manual offset math.)
 *
 * Holiday handling
 *   This helper does NOT know about NSE holidays (Republic Day,
 *   Independence Day, Diwali Muhurat, etc.). On a weekday holiday
 *   it will incorrectly report "market open". That's acceptable
 *   for the pre-launch sprint — chart will briefly show
 *   "Reconnecting…" on those days; users can dismiss / ignore.
 *
 *   // TODO: integrate NSE holiday calendar (post-launch). NSE
 *   // publishes a yearly holiday list; cache locally and check
 *   // alongside the weekday/time gate.
 */

export const NSE_OPEN_MINUTE = 9 * 60 + 15; // 09:15 IST
export const NSE_CLOSE_MINUTE = 15 * 60 + 30; // 15:30 IST

interface ISTComponents {
  weekday: string; // "Mon" | "Tue" | ... | "Sun"
  hour: number;
  minute: number;
}

function getISTComponents(now: Date): ISTComponents {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = fmt.formatToParts(now);
  const weekday =
    parts.find((p) => p.type === "weekday")?.value ?? "Sun";
  const hour = Number(parts.find((p) => p.type === "hour")?.value ?? 0);
  const minute = Number(
    parts.find((p) => p.type === "minute")?.value ?? 0,
  );
  // Some ``Intl`` implementations emit "24" for midnight under
  // ``hour12: false``; normalise to the standard 0..23 range.
  return { weekday, hour: hour === 24 ? 0 : hour, minute };
}

/**
 * Returns ``true`` when ``now`` is within NSE regular trading
 * hours: Monday–Friday, 09:15:00 ≤ t ≤ 15:30:00 IST.
 *
 * ``now`` defaults to ``new Date()``; pass an explicit ``Date``
 * to test the helper without mocking the system clock.
 */
export function isMarketOpen(now: Date = new Date()): boolean {
  const { weekday, hour, minute } = getISTComponents(now);
  if (weekday === "Sat" || weekday === "Sun") return false;
  const minutes = hour * 60 + minute;
  return minutes >= NSE_OPEN_MINUTE && minutes <= NSE_CLOSE_MINUTE;
}

/**
 * Format a NIFTY-style price for the "Last close" pill using
 * Indian-locale grouping (lakh / crore separators) and a ₹
 * prefix. Returns ``null`` for non-finite inputs so the caller
 * can decide whether to render the pill at all.
 *
 * Example: ``formatLastClosePrice(22459.5)`` → ``"₹22,459.50"``.
 */
export function formatLastClosePrice(price: number | null): string | null {
  if (price === null || !Number.isFinite(price)) return null;
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price);
}
