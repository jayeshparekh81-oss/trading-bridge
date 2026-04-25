/**
 * AlgoMitra Live Reaction System — local state.
 *
 * No backend changes. All state in localStorage so it survives page
 * reloads but stays per-browser. Three concerns split out:
 *
 * - **Daily baseline**: snapshot of `total_pnl` taken on the first
 *   read of an IST trading day. Today's running P&L ≈ current −
 *   baseline. Auto-rolls when the IST date changes.
 * - **Reaction history**: which triggers fired today, when, and how
 *   many times. Drives cooldown + daily cap.
 * - **Notification preference**: All / Important only / Off.
 */

const NS = "tb_algomitra_live";

const KEY_BASELINE_PREFIX = `${NS}_baseline_`; // + YYYY-MM-DD (IST)
const KEY_HISTORY = `${NS}_history`;
const KEY_DISMISSALS = `${NS}_dismissals`;
const KEY_NOTIF_MODE = `${NS}_notif_mode`;

const COOLDOWN_MS_DEFAULT = 30 * 60_000; // 30 minutes
const DAILY_CAP_DEFAULT = 5;
const DISMISSAL_BLACKOUT = 3; // 3 manual dismissals in a row → quiet for the day

export type NotifMode = "all" | "important" | "off";

// ─── IST date helpers ────────────────────────────────────────────────────

function istDateKey(date: Date = new Date()): string {
  // Asia/Kolkata is UTC+5:30, no DST.
  const istMs = date.getTime() + 5.5 * 60 * 60_000;
  return new Date(istMs).toISOString().slice(0, 10); // YYYY-MM-DD
}

// ─── Daily baseline ─────────────────────────────────────────────────────

export interface BaselineRead {
  baseline: number;
  istDate: string;
  isFirstReadToday: boolean;
}

/**
 * Read or initialise today's P&L baseline.
 *
 * On the first call of an IST day, captures ``currentTotalPnl`` as
 * the baseline and returns ``isFirstReadToday: true``. Subsequent
 * calls return the same baseline until IST midnight.
 */
export function getDailyBaseline(currentTotalPnl: number): BaselineRead {
  if (typeof window === "undefined") {
    return { baseline: currentTotalPnl, istDate: istDateKey(), isFirstReadToday: true };
  }
  const istDate = istDateKey();
  const key = KEY_BASELINE_PREFIX + istDate;
  const stored = localStorage.getItem(key);
  if (stored !== null) {
    return { baseline: Number(stored), istDate, isFirstReadToday: false };
  }
  // First read of this IST day — snapshot and clear yesterday's history.
  localStorage.setItem(key, String(currentTotalPnl));
  pruneOldBaselines(istDate);
  resetDailyHistory();
  return { baseline: currentTotalPnl, istDate, isFirstReadToday: true };
}

function pruneOldBaselines(today: string): void {
  // Keep the last 3 IST days only — protects against indefinite localStorage growth.
  const keep = new Set<string>();
  keep.add(today);
  const yesterday = new Date(Date.now() - 86_400_000);
  keep.add(istDateKey(yesterday));
  const dayBefore = new Date(Date.now() - 2 * 86_400_000);
  keep.add(istDateKey(dayBefore));
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (!k || !k.startsWith(KEY_BASELINE_PREFIX)) continue;
    const date = k.slice(KEY_BASELINE_PREFIX.length);
    if (!keep.has(date)) localStorage.removeItem(k);
  }
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

function resetDailyHistory(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(KEY_HISTORY);
  localStorage.removeItem(KEY_DISMISSALS);
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

function readDismissals(): number {
  if (typeof window === "undefined") return 0;
  const raw = localStorage.getItem(KEY_DISMISSALS);
  return raw ? parseInt(raw, 10) || 0 : 0;
}

export function recordDismissal(): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(KEY_DISMISSALS, String(readDismissals() + 1));
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
