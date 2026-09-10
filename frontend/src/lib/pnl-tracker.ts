/**
 * AlgoMitra Live Reaction System — local state.
 *
 * Three concerns split out:
 *
 * - **Today's P&L**: DERIVED from the `curve` the server already sends —
 *   see `deriveTodayPnl`. Nothing about it is stored.
 * - **Reaction history**: which triggers fired today, when, and how
 *   many times. Drives cooldown + daily cap. localStorage, per-browser.
 * - **Notification preference**: All / Important only / Off.
 *
 * ⚠️ THE DELETED BASELINE — why "today's P&L" is never stored
 * ──────────────────────────────────────────────────────────
 * This module used to snapshot CUMULATIVE `total_pnl` on the first read of
 * an IST day and call `current − baseline` "today". The stored key named
 * the DATE and nothing about the dataset, so it silently assumed the
 * cumulative series behind it never changed shape.
 *
 * On 2026-09-09 the tracking cut-off archived the pre-cut history and
 * `total_pnl` moved from -195,830.51 to 0.00. The baseline from earlier
 * that morning was still -195,830.51, so "today" evaluated to
 * +195,830.51 and the coach announced a ₹1.96 lakh KILLER DAY over a
 * loss. Nothing was corrupt; the subtraction was between two numbers
 * that had stopped meaning the same thing.
 *
 * The replacement does not subtract across time at all: today's P&L is the
 * SUM OF TODAY'S OWN ROWS, taken from the same response, already filtered
 * by the same cut-off server-side. Consistent by construction — there is no
 * stale half of the sum left to invalidate, so no epoch-invalidation
 * mechanism is needed either. Do not reintroduce a stored baseline.
 */

const NS = "tb_algomitra_live";

/** Dead key from the deleted baseline mechanism — purged, never written. */
const KEY_LEGACY_BASELINE_PREFIX = `${NS}_baseline_`; // + YYYY-MM-DD (IST)
const KEY_HISTORY = `${NS}_history`;
const KEY_DISMISSALS = `${NS}_dismissals`;
const KEY_NOTIF_MODE = `${NS}_notif_mode`;

const COOLDOWN_MS_DEFAULT = 30 * 60_000; // 30 minutes
const DAILY_CAP_DEFAULT = 5;
const DISMISSAL_BLACKOUT = 3; // 3 manual dismissals in a row → quiet for the day

export type NotifMode = "all" | "important" | "off";

// ─── IST date helpers ────────────────────────────────────────────────────

/** The IST calendar day (``YYYY-MM-DD``). Exported so every "aaj" on the
 *  platform — the P&L baseline here, the Overview signal count — cuts the
 *  day at the same instant. */
export function istDateKey(date: Date = new Date()): string {
  // Asia/Kolkata is UTC+5:30, no DST.
  const istMs = date.getTime() + 5.5 * 60 * 60_000;
  return new Date(istMs).toISOString().slice(0, 10); // YYYY-MM-DD
}

// ─── Today's P&L, derived from the server's own rows ────────────────────

/** One priced round trip as `GET /users/me/trades/stats` sends it. */
export interface CurveRow {
  position_id?: string;
  symbol?: string;
  /** ISO 8601 instant WITH an offset. */
  closed_at?: string | null;
  /** Decimal as a string, e.g. "-1234.5600". */
  pnl?: string | number | null;
  attribution?: string | null;
}

export interface TodayPnl {
  /** Net P&L of the round trips that closed in the current IST day. */
  amount: number;
  /** How many rows made that number. Always ≥ 1 — see the null contract. */
  rows: number;
}

/**
 * An ISO instant must carry a zone. A bare "2026-09-07T15:04:06" is parsed
 * by JS as the BROWSER'S local time, which would file a trade under the
 * wrong IST day for anyone outside India — so we refuse to guess.
 */
const HAS_OFFSET = /(?:Z|[+-]\d{2}:?\d{2})$/i;

/**
 * A decimal the server sent, or null when the value is not one.
 *
 * Deliberately strict: see the call site. A blank, a null, a boolean or an
 * object must NEVER coerce to zero here.
 */
function readDecimal(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const n = Number(trimmed);
  return Number.isFinite(n) ? n : null;
}

/** The IST day an instant belongs to, or null when we cannot place it. */
function istDayOfInstant(iso: string): string | null {
  const trimmed = iso.trim();
  if (!HAS_OFFSET.test(trimmed)) return null;
  const ms = Date.parse(trimmed);
  if (!Number.isFinite(ms)) return null;
  return istDateKey(new Date(ms));
}

/**
 * Today's P&L — the sum of the `curve` rows that closed in the current IST
 * day, cut at the same instant as every other "aaj" on the platform
 * (`istDateKey`).
 *
 * **`null` means SILENCE, and silence is never zero.** Three different
 * facts collapse to it, and none of them may be printed as "₹0":
 *
 *   no curve / not an array  → we have not read the day
 *   no rows closed today     → nothing PRICED closed; the day may still hold
 *                              unpriced or `human_interfered` round trips,
 *                              which the server deliberately omits from
 *                              `curve` rather than folding in as zero
 *   any row unreadable       → a row we cannot place in a day or cannot
 *                              value might BE today's; a sum without it
 *                              would be a confident wrong number
 *
 * A caller that renders `?? 0` here has reintroduced the bug in a new shape.
 */
export function deriveTodayPnl(
  curve: unknown,
  now: Date = new Date(),
): TodayPnl | null {
  if (!Array.isArray(curve)) return null;

  const today = istDateKey(now);
  let amount = 0;
  let rows = 0;

  for (const raw of curve) {
    if (raw === null || typeof raw !== "object") return null;
    const row = raw as CurveRow;

    if (typeof row.closed_at !== "string") return null;
    const day = istDayOfInstant(row.closed_at);
    if (day === null) return null;
    if (day !== today) continue;

    // `Number(null)`, `Number("")` and `Number(" ")` are all 0 and all
    // finite — a value we cannot read would slip in as a silent zero and
    // quietly drag the day's number toward flat. Only a real number or a
    // non-blank numeric string counts.
    const pnl = readDecimal(row.pnl);
    if (pnl === null) return null;

    amount += pnl;
    rows += 1;
  }

  if (rows === 0) return null;
  return { amount, rows };
}

/**
 * Remove every key the deleted baseline mechanism left behind.
 *
 * Idempotent and safe to call on every mount. Without it a browser that saw
 * the old build keeps a `..._baseline_YYYY-MM-DD` key forever — dead weight
 * that also makes the bug look live to anyone reading localStorage.
 */
export function purgeLegacyBaselines(): void {
  if (typeof window === "undefined") return;
  const doomed: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k && k.startsWith(KEY_LEGACY_BASELINE_PREFIX)) doomed.push(k);
  }
  for (const k of doomed) localStorage.removeItem(k);
}

// ─── Reaction history (cooldown + cap) ──────────────────────────────────

interface ReactionHistoryEntry {
  triggerId: string;
  shownAt: number; // ms epoch
}

interface ReactionHistory {
  istDate: string;
  entries: ReactionHistoryEntry[];
}

function readHistory(): ReactionHistory {
  if (typeof window === "undefined") {
    return { istDate: istDateKey(), entries: [] };
  }
  const today = istDateKey();
  const raw = localStorage.getItem(KEY_HISTORY);
  if (!raw) return { istDate: today, entries: [] };
  try {
    const parsed = JSON.parse(raw) as ReactionHistory;
    if (parsed.istDate !== today) {
      // Old day's history — drop.
      return { istDate: today, entries: [] };
    }
    return parsed;
  } catch {
    return { istDate: today, entries: [] };
  }
}

function writeHistory(h: ReactionHistory): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY_HISTORY, JSON.stringify(h));
}

export interface ReactionGate {
  triggerId: string;
  /** Important reactions bypass cooldown / cap (big losses, big profits). */
  isImportant: boolean;
  /** Cooldown in ms; defaults to 30 min if omitted. */
  cooldownMs?: number;
}

/**
 * Decide whether a reaction should be shown right now, applying:
 *   1. Notification mode (off → never; important → only important).
 *   2. Same-trigger cooldown (default 30 min).
 *   3. Daily cap (default 5 reactions per day; important bypasses cap).
 *   4. Dismissal blackout (after 3 manual dismissals → quiet for the day,
 *      important reactions still surface).
 */
export function canShowReaction(gate: ReactionGate, mode: NotifMode): boolean {
  if (mode === "off") return false;
  if (mode === "important" && !gate.isImportant) return false;

  const history = readHistory();
  const now = Date.now();

  // Daily cap (important bypasses).
  if (!gate.isImportant && history.entries.length >= DAILY_CAP_DEFAULT) {
    return false;
  }

  // Same-trigger cooldown (important bypasses).
  const cooldown = gate.cooldownMs ?? COOLDOWN_MS_DEFAULT;
  if (!gate.isImportant) {
    const last = history.entries
      .filter((e) => e.triggerId === gate.triggerId)
      .pop();
    if (last && now - last.shownAt < cooldown) return false;
  }

  // Dismissal blackout (important bypasses).
  if (!gate.isImportant && readDismissals() >= DISMISSAL_BLACKOUT) {
    return false;
  }

  return true;
}

export function recordReaction(triggerId: string): void {
  const history = readHistory();
  history.entries.push({ triggerId, shownAt: Date.now() });
  // Trim to last 20 — defensive ceiling.
  if (history.entries.length > 20) history.entries.splice(0, history.entries.length - 20);
  writeHistory(history);
}

// ─── Dismissal tracking ─────────────────────────────────────────────────

/**
 * The dismissal counter is DAY-STAMPED.
 *
 * It used to be a bare number cleared as a side effect of taking the daily
 * baseline. With the baseline gone, an undated counter would have made the
 * 3-strike blackout permanent — the coach would go quiet one afternoon and
 * stay quiet forever. The stamp is read here, so the rollover cannot be
 * forgotten by a caller. A value written by the old build fails `JSON.parse`
 * and reads as zero, which is the correct fresh state.
 */
function readDismissals(): number {
  if (typeof window === "undefined") return 0;
  const raw = localStorage.getItem(KEY_DISMISSALS);
  if (!raw) return 0;
  try {
    const parsed = JSON.parse(raw) as { istDate?: string; count?: number };
    if (parsed.istDate !== istDateKey()) return 0;
    return typeof parsed.count === "number" && parsed.count > 0 ? parsed.count : 0;
  } catch {
    return 0;
  }
}

export function recordDismissal(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(
    KEY_DISMISSALS,
    JSON.stringify({ istDate: istDateKey(), count: readDismissals() + 1 }),
  );
}

export function clearDismissals(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(KEY_DISMISSALS);
}

// ─── Notification preference ────────────────────────────────────────────

export function getNotifMode(): NotifMode {
  if (typeof window === "undefined") return "all";
  const v = localStorage.getItem(KEY_NOTIF_MODE);
  return v === "all" || v === "important" || v === "off" ? v : "all";
}

export function setNotifMode(mode: NotifMode): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY_NOTIF_MODE, mode);
}
