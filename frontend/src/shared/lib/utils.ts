import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(
  amount: number,
  opts?: { showSign?: boolean; compact?: boolean }
): string {
  const sign = opts?.showSign && amount > 0 ? "+" : "";
  if (opts?.compact && Math.abs(amount) >= 100000) {
    return `${sign}\u20B9${(amount / 100000).toFixed(1)}L`;
  }
  return `${sign}\u20B9${Math.abs(amount).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

/** What every surface prints for a value it does not know. */
export const UNKNOWN_DASH = "—";

/**
 * Format a PRICE, or print "—" when we do not know it.
 *
 * ⚠️ Prices only — never P&L. A P&L of exactly zero is a real, meaningful
 * fact (breakeven) and must still render as ₹0. A PRICE of exactly zero is
 * not a price: the backend writes `Decimal("0")` as its "no price in the
 * payload" sentinel, so a zero here means "unknown", never "free".
 *
 * WHY A DEDICATED HELPER (defect, 2026-09-09, founder's own account)
 * ──────────────────────────────────────────────────────────────────
 * Every call site guarded with a plain truthiness check:
 *
 *     {p.avg_entry_price ? formatCurrency(Number(p.avg_entry_price)) : "—"}
 *
 * `avg_entry_price` arrives as a STRING (Postgres `Numeric(18,4)` serialised),
 * so the sentinel reaches the browser as `"0.0000"` — a NON-EMPTY string, and
 * therefore TRUTHY. The guard never fired and the cell printed a confident
 * `₹0` entry price on a real futures position. `Number("0.0000")` is falsy,
 * but nothing ever converted before testing.
 *
 * Accepts the raw wire value (string | number | null) precisely so no call
 * site has to remember to convert first — that conversion was the bug.
 */
export function formatPriceOrUnknown(
  raw: string | number | null | undefined,
): string {
  if (raw === null || raw === undefined || raw === "") return UNKNOWN_DASH;
  const n = Number(raw);
  // NaN → we were sent something that is not a number at all.
  // 0 → the backend's "no price" sentinel. Neither is a price.
  if (!Number.isFinite(n) || n === 0) return UNKNOWN_DASH;
  return formatCurrency(n);
}

export function formatPercent(value: number, decimals = 1): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

export function relativeTime(dateStr: string): string {
  if (!dateStr) return "";
  const then = new Date(dateStr).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  // Clamp future timestamps (clock skew) to "just now" — never show
  // "-3m ago" to a user.
  if (diff < 60_000) return "just now";
  const mins = Math.floor(diff / 60_000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}
