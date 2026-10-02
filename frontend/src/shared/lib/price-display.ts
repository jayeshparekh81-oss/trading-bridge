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
 * same words an absent value does ("daam nahi mila" — was an em-dash until 26 Sep).
 *
 * Prices arrive as STRINGS (exact DB text). We inspect the value numerically
 * to spot the sentinel, but we RENDER the original string — never a reformatted
 * float, which would silently re-round money.
 */

import { formatCurrency } from "@/shared/lib/utils";
import { NO_PRICE_WORDS, NOT_SET } from "@/shared/lib/unknown";

/** True when this stored value is the "no price recorded" sentinel. */
export function isUnknownPrice(raw: string | null | undefined): boolean {
  if (raw === null || raw === undefined || raw.trim() === "") return true;
  const n = Number(raw);
  return !Number.isFinite(n) || n === 0;
}

/** Words, not a dash (founder's rule, 26 Sep, point 10): a dash in a price column reads like data. */
export const NO_PRICE = NO_PRICE_WORDS;

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
  /** The words for "no price" in the customer's language (2 Oct 2026); the Hinglish source stays the default. */
  unknownWords: string = NO_PRICE,
): string {
  const text = raw === null || raw === undefined ? null : String(raw);
  return isUnknownPrice(text) ? unknownWords : formatCurrency(Number(raw));
}

/**
 * A LEVEL the strategy may simply not have (a target, a stop): absent or the 0
 * sentinel means nobody set one — "set nahi", not "price not received".
 */
export function formatLevelOrUnset(
  raw: string | number | null | undefined,
  /** The words for "nobody set one" in the customer's language (2 Oct 2026); the Hinglish source stays the default. */
  unsetWords: string = NOT_SET,
): string {
  const text = raw === null || raw === undefined ? null : String(raw);
  return isUnknownPrice(text) ? unsetWords : formatCurrency(Number(raw));
}
