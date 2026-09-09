/**
 * Rendering a stored price WITHOUT inventing one.
 *
 * `_simulate_fill` (backend/app/services/strategy_executor.py) is explicit
 * about this: when the TradingView payload carries no price, it stores
 * `Decimal("0")` and the docstring says the position manager seeds the real
 * value from LTP later. So a `0` in a price column is a SENTINEL meaning
 * "not known", not a fill at zero rupees.
 *
 * Nothing trades at ₹0. Rendering "0.0000" in a column headed Price or Entry
 * therefore states a number that never happened — the same class of harm as an
 * invented P&L, which is why this screen shows none. So a zero renders as the
 * same em-dash an absent value does.
 *
 * Prices arrive as STRINGS (exact DB text). We inspect the value numerically
 * to spot the sentinel, but we RENDER the original string — never a reformatted
 * float, which would silently re-round money.
 */

import { formatCurrency } from "@/shared/lib/utils";

/** True when this stored value is the "no price recorded" sentinel. */
export function isUnknownPrice(raw: string | null | undefined): boolean {
  if (raw === null || raw === undefined || raw.trim() === "") return true;
  const n = Number(raw);
  return !Number.isFinite(n) || n === 0;
}

export const NO_PRICE = "—";

/**
 * The display string for a stored price: the ORIGINAL text when it is a real
 * price, an em-dash when it is absent or the zero sentinel.
 */
export function displayPrice(raw: string | null | undefined): string {
  return isUnknownPrice(raw) ? NO_PRICE : (raw as string);
}

/**
 * The same rule, rendered as ₹ currency for tabular surfaces.
 *
 * Two renderings of one fact, ONE predicate. `displayPrice` keeps the exact
 * DB text (the marketplace card must never re-round money); a table column
 * headed "Entry" wants ₹3,470. Both ask `isUnknownPrice`, so the sentinel can
 * never be a price on one screen and a dash on another.
 *
 * PRICES ONLY. A P&L of exactly zero is a real fact (breakeven) and must keep
 * rendering as ₹0 — never route a P&L through here.
 *
 * The /positions table used `p.avg_entry_price ? … : "—"` instead. The
 * sentinel arrives as the STRING "0.0000", which is truthy, so the guard never
 * fired and it printed a confident ₹0 entry on a real futures position
 * (founder's own account, 2026-09-09).
 */
export function formatPriceOrUnknown(
  raw: string | number | null | undefined,
): string {
  const text = raw === null || raw === undefined ? null : String(raw);
  return isUnknownPrice(text) ? NO_PRICE : formatCurrency(Number(raw));
}
