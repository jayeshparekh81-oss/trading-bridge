import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(
  amount: number,
  opts?: { showSign?: boolean; compact?: boolean }
): string {
  // A LOSS MUST SHOW ITS MINUS SIGN.
  //
  // This rendered `Math.abs(amount)` with no leading "-", so a -198,265.66
  // realised loss printed as "₹1,98,266" — a number that reads as a gain.
  // Only red text distinguished it, and colour alone is not enough on a money
  // surface: it is lost to copy-paste, to grayscale, to colour-blind readers,
  // and to anyone scanning a column of figures. The two branches also
  // disagreed — the compact branch divided the SIGNED amount, so one loss was
  // "-₹1.9L" compact and "₹1,98,266" full. One number, two stories.
  //
  // "+" still requires opts.showSign (a plus is a flourish). "-" never does
  // (a minus is the fact).
  const sign = amount < 0 ? "-" : opts?.showSign && amount > 0 ? "+" : "";
  const magnitude = Math.abs(amount);
  if (opts?.compact && magnitude >= 100000) {
    return `${sign}\u20B9${(magnitude / 100000).toFixed(1)}L`;
  }
  return `${sign}\u20B9${magnitude.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
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
