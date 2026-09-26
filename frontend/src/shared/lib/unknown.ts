/**
 * THE WORDS for a value we do not have (founder's rule, 26 Sep 2026, point 10:
 * "NOT MEASURED says NOT MEASURED, never a zero or a dash that reads like a real
 * number"). One source: a screen never invents its own dash.
 *
 * Pick by WHY the value is missing — each says what the customer is looking at:
 */

/** A number we never measured (or could not read this time). */
export const NOT_MEASURED = "NOT MEASURED";

/** A price the broker / signal never gave us (the stored 0 sentinel included). */
export const NO_PRICE_WORDS = "daam nahi mila";

/** A level nobody set (no target, no stop on this row). */
export const NOT_SET = "set nahi";

/** Something the broker has not reported yet (an order id, a status, a fill time). */
export const NOT_REPORTED = "abhi nahi aaya";

/** A count or list we could not load — never a confident 0. */
export const NOT_LOADED = "load nahi hua";
