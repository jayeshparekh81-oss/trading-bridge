/**
 * The first-timer GUIDED PATH — client side (founder, 26 Sep 2026).
 *
 *   signup → Dhan jodo → strategy → vehicle (only FUTURES open) → strike (OTM default,
 *   not shown for futures) → size + max risk → summary → confirm → running
 *
 * ONE SOURCE PER FACT: the server (`/customer-lane/guided/*`) owns the order of the
 * screens, the copy, the defaults, every number and every error sentence. This file only
 * carries the payload types, the calls, the never-stuck error parsing, and a small local
 * mirror of "which step was I on" so a closed tab re-opens on the right screen even
 * before the network answers. The mirror is never believed over the server.
 *
 * FLAG: `NEXT_PUBLIC_CUSTOMER_GUIDED_PATH` — unset/"0" = OFF = `/start` renders the honest
 * "not switched on" line and nothing else.
 */

import { api, ApiError, setTokens } from "@/shared/api/client";

export const GUIDED_FLAG = "NEXT_PUBLIC_CUSTOMER_GUIDED_PATH";

/**
 * OFF unless exactly "1". Read at call time so tests can flip it.
 *
 * ⚠ THIS ALONE NEVER DECIDES what a customer sees (the switch-on trap, founder 26 Sep):
 * the frontend flag on with the backend flag off would send a new customer to a /start
 * whose API does not exist. Every screen decision goes through `guidedPathLive()` /
 * `useGuidedPathLive()`, which also demands the backend's own live readiness.
 */
export function guidedPathEnabled(): boolean {
  // Literal spelling on purpose: the only form Next's docs promise to inline into the
  // browser bundle (see customerVehiclesEnabled).
  return process.env.NEXT_PUBLIC_CUSTOMER_GUIDED_PATH === "1";
}

export const GUIDED_STEPS = [
  "SIGNUP", "BROKER", "STRATEGY", "VEHICLE", "STRIKE", "SIZE", "SUMMARY", "CONFIRM", "RUNNING",
] as const;
export type GuidedStep = (typeof GUIDED_STEPS)[number];

export function isGuidedStep(v: unknown): v is GuidedStep {
  return typeof v === "string" && (GUIDED_STEPS as readonly string[]).includes(v);
}

// ── payloads (mirror app/api/customer_guided.py) ─────────────────────────────

export interface ProgressItem { n: number; step: GuidedStep; title: string; state: "DONE" | "CURRENT" | "TODO" | "NOT_NEEDED" }
export interface Option { name: string; label_hi: string; open: boolean; why?: string }
export interface StrategyOption { id: string; title: string; instrument?: string | null; price_inr?: string | null }
export type Money = number | "NOT MEASURED";
export interface Capital {
  minimum_capital: Money; worst_day: Money; max_drawdown: Money; margin?: Money;
  basis?: string; worst_day_basis?: string; max_drawdown_basis?: string; margin_as_of?: string | null;
  margin_as_of_human?: string;
  /** where each number comes from, in the customer's words (walk 1: the engineering basis was jargon) */
  plain?: { minimum_capital: string; worst_day: string; max_drawdown: string };
  margin_stale?: boolean | null; trades?: number | string; period?: string;
}
export interface SummaryNumber { label: string; value: Money; basis: string }
export interface Summary {
  strategy: string; vehicle: string; lots: number; quantity: number | null; moneyness: string | null;
  will_do: string[]; will_never_do: string[]; not_yet: string[]; numbers: SummaryNumber[]; market_line: string;
}
export interface Screen {
  step: GuidedStep; title: string; decision: string; why: string; default_note: string;
  broker_state?: string; where_to_find?: string;
  options?: Array<Option | StrategyOption>; selected?: string | null; empty_line?: string;
  applies?: boolean; applies_line?: string;
  lots?: number; lot_size?: number | null; lot_choices?: number[]; capital?: Capital;
  max_daily_loss_default?: number | null; max_daily_loss_inr?: number | null;
  by_lots?: Record<string, Capital & { max_daily_loss_default: number | null; shares: number | null }>;
  summary?: Summary; acknowledged?: boolean;
}
export interface GuideReply { text: string; kind: string; flags: string[]; warnings: string[] }
export interface Draft {
  step: GuidedStep; strategy_id: string | null; vehicle: string; moneyness: string; lots: number;
  max_daily_loss_inr: number | null; acknowledged: boolean; visited: string[];
}
export interface GuidedState {
  step: GuidedStep; progress: ProgressItem[]; screen: Screen; back?: GuidedStep | null; draft?: Draft;
  warnings?: string[]; guide: GuideReply; market?: { open: boolean; line: string };
  broker_state?: string; running?: string | null;
}
export interface Running {
  strategy: string | null; running: boolean; stopped: boolean; is_paper: boolean; paper_line: string; lots: number | null;
  market: { open: boolean; line: string };
  broker: { state: string; line: string; action: ErrorAction | null };
  positions: Array<{ symbol: string; side: string; quantity: number; avg_price: string | null; opened_at: string | null }>;
  positions_line: string;
  /** "paper record" · "GET /v2/positions" (Dhan's own read) · "NOT MEASURED" — never our rows for a real account */
  positions_source?: string;
  stop: { verdict: string; line: string; verified_at: string | null; source: string };
  today_pnl: { line: string; measured: boolean; net_inr: string | null; gross_inr: string | null; billed_charges_inr: string | null };
  stop_everything: { enabled: boolean };
}
export interface StopPreview { confirm_token: string; expires_in_s: number; lines: string[]; positions: number; paper: boolean }
export interface StopResult { stopped: boolean; lines: string[]; restart_line: string }

// ── the never-stuck envelope ─────────────────────────────────────────────────

export interface ErrorAction { label: string; href: string | null; step: GuidedStep | null }
export interface CustomerError {
  kind: string; what_happened: string; what_it_means: string; what_to_do: string;
  action: ErrorAction | null; back: ErrorAction | null; contact: { who: string; send: string; href: string } | null;
}

const SUPPORT = { who: "TRADETRI support — app ke andar Help page par ticket banao", href: "/help",
  send: "Screen ka naam, kya dabaya tha, aur kitne baje hua — bas itna. Password ya Dhan ki chabi (token) KABHI mat bhejna." };

/** The words a customer sees when the NETWORK itself failed — no server envelope exists. */
export function offlineError(): CustomerError {
  return {
    kind: "OFFLINE", what_happened: "Internet ya hamara server abhi jawab nahi de raha.",
    what_it_means: "Aapka kaam save hai — kuch khoya nahi, koi order nahi gaya.",
    what_to_do: "Internet check karo aur 'Dobara try karo' dabao.",
    action: { label: "Dobara try karo", href: null, step: null }, back: null, contact: SUPPORT,
  };
}

/**
 * Turn ANY thrown thing into the envelope. The server's own envelope wins; anything else
 * (a network drop, an old server, a bug) becomes a plain line with a way forward — never
 * the raw `detail`, a status code or a stack.
 */
export function toCustomerError(err: unknown, screen = "guided"): CustomerError {
  if (err instanceof ApiError) {
    const env = (err.data as { error?: CustomerError } | undefined)?.error;
    if (env && typeof env.what_to_do === "string") return env;
    if (err.status === 0) return offlineError();
    if (err.status === 401) {
      return {
        kind: "SIGNED_OUT", what_happened: "Aap sign-out ho gaye (session khatam).",
        what_it_means: "Aapka kaam save hai — dobara login karte hi wahi kadam khulega.", what_to_do: "Login karo.",
        action: { label: "Login", href: "/login?next=/start", step: null }, back: null, contact: null,
      };
    }
  }
  return {
    kind: "UNKNOWN", what_happened: "Hamari taraf kuch gadbad hui.",
    what_it_means: "Aapka kaam save hai. Paisa ya order par koi asar nahi hua.",
    what_to_do: "1 minute baad dobara try karo. Phir bhi na chale to Support par batao.",
    action: { label: "Dobara try karo", href: null, step: null }, back: null,
    contact: { ...SUPPORT, send: `${SUPPORT.send} (screen: ${screen})` },
  };
}

/** Signup errors come from /auth/*, which has no envelope — mapped here, ONCE. */
export function signupError(err: unknown): CustomerError {
  if (err instanceof ApiError) {
    if (err.status === 409) {
      return {
        kind: "EMAIL_TAKEN", what_happened: "Is email se account pehle se bana hua hai.",
        what_it_means: "Naya account nahi chahiye — purane se hi aage badh sakte ho.",
        what_to_do: "Login karo; login ke baad yahi guide wahin se chalega.",
        action: { label: "Login karo", href: "/login?next=/start", step: null }, back: null, contact: null,
      };
    }
    if (err.status === 400 && /password/i.test(err.detail)) {
      return {
        kind: "WEAK_PASSWORD", what_happened: "Password kamzor hai.",
        what_it_means: "Kamzor password se koi aur aapka account khol sakta hai.",
        what_to_do: "Kam se kam 8 akshar: ek bada (A-Z), ek chhota (a-z), ek number, ek chinh (@ # !). Naam ya email ka hissa mat daalo.",
        action: { label: "Password badlo", href: null, step: "SIGNUP" }, back: null, contact: null,
      };
    }
    if (err.status === 422) {
      return {
        kind: "BAD_FORM", what_happened: "Email ya password ka format sahi nahi.",
        what_it_means: "Account abhi bana nahi.", what_to_do: "Email jaisa naam@gmail.com likho aur password 8+ akshar ka rakho.",
        action: { label: "Theek karo", href: null, step: "SIGNUP" }, back: null, contact: null,
      };
    }
  }
  return toCustomerError(err, "signup");
}

/** The password rules, shown BEFORE the customer types (not after a refusal). */
export const PASSWORD_RULES: Array<{ label: string; ok: (pw: string, ctx: { email: string; name: string }) => boolean }> = [
  { label: "8 ya zyada akshar", ok: (pw) => pw.length >= 8 },
  { label: "Ek bada akshar (A-Z)", ok: (pw) => /[A-Z]/.test(pw) },
  { label: "Ek chhota akshar (a-z)", ok: (pw) => /[a-z]/.test(pw) },
  { label: "Ek number (0-9)", ok: (pw) => /\d/.test(pw) },
  { label: "Ek chinh (@ # ! jaisa)", ok: (pw) => /[^A-Za-z0-9]/.test(pw) },
  {
    label: "Naam ya email ka hissa nahi",
    ok: (pw, { email, name }) => {
      const local = email.split("@")[0]?.toLowerCase() ?? "";
      const nm = name.replace(/\s+/g, "").toLowerCase();
      const p = pw.toLowerCase();
      return !(local.length >= 3 && p.includes(local)) && !(nm.length >= 3 && p.includes(nm));
    },
  },
];

// ── local mirror (resume before the network answers; never believed over it) ──

const MIRROR_KEY = "tb_guided_last_step";

export function rememberStep(step: GuidedStep): void {
  try { if (typeof window !== "undefined") localStorage.setItem(MIRROR_KEY, step); } catch { /* private mode */ }
}
export function lastStep(): GuidedStep | null {
  try {
    const v = typeof window !== "undefined" ? localStorage.getItem(MIRROR_KEY) : null;
    return isGuidedStep(v) ? v : null;
  } catch { return null; }
}

// ── money in the customer's own digits ───────────────────────────────────────

/** Indian grouping (6,31,765). "NOT MEASURED" stays the literal words. */
export function inr(v: Money | string | null | undefined): string {
  if (v === "NOT MEASURED" || v === null || v === undefined || v === "") return "NOT MEASURED";
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return "NOT MEASURED";
  return `Rs ${new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(Math.round(n))}`;
}

// ── calls ────────────────────────────────────────────────────────────────────

const BASE = "/customer-lane/guided";

export const guidedApi = {
  publicStart: () => api.get<GuidedState>(`${BASE}/public`),
  state: () => api.get<GuidedState>(`${BASE}/state`),
  choose: (step: GuidedStep, choice: Record<string, unknown> = {}) => api.put<GuidedState>(`${BASE}/draft`, { step, choice }),
  back: (step: GuidedStep) => api.post<GuidedState>(`${BASE}/back`, { step }),
  broker: (client_id: string, access_token: string) => api.post<GuidedState>(`${BASE}/broker`, { client_id, access_token }),
  ask: (step: GuidedStep, question: string) =>
    step === "SIGNUP"
      ? api.post<GuideReply>(`${BASE}/public/ask`, { step, question }, true)
      : api.post<GuideReply>(`${BASE}/ask`, { step, question }),
  restart: () => api.post<GuidedState>(`${BASE}/restart`, {}),
  confirm: () => api.post<{ started: boolean; market: { open: boolean; line: string }; is_paper: boolean }>(`${BASE}/confirm`, { acknowledged: true }),
  running: () => api.get<Running>(`${BASE}/running`),
  stopPreview: () => api.post<StopPreview>(`${BASE}/stop/preview`, {}),
  stop: (confirm_token: string) => api.post<StopResult>(`${BASE}/stop`, { confirm_token }),
  async signup(data: { full_name: string; email: string; password: string }): Promise<void> {
    await api.post("/auth/register", data, true);
    const t = await api.post<{ access_token: string; refresh_token: string }>("/auth/login",
      { email: data.email, password: data.password }, true);
    setTokens(t.access_token, t.refresh_token);
  },
};

// ── THE SWITCH-ON INTERLOCK (founder, 26 Sep 2026) ───────────────────────────
//
// "The backend and frontend guided-path flags must never be on separately. Make that
// impossible, not just documented." The frontend flag is necessary, never sufficient: the
// new path is shown only when the BACKEND answers, live, that its guided API is mounted and
// ready (GET /customer-lane/guided/readiness → {"api": "guided-path", "ready": true}).
// A 404 (backend flag off → router not mounted), an error, a timeout, an old server, a wrong
// shape or `ready: false` all mean NOT READY → the customer silently keeps the current
// onboarding. Never a dead end.

export const READINESS_PATH = `${BASE}/readiness`;
/** A readiness answer slower than this is NOT READY (the customer is never kept waiting). */
export const READINESS_TIMEOUT_MS = 3000;
/** One answer is reused for this long, so a page change does not ask again. */
export const READINESS_CACHE_MS = 60_000;

export type GuidedLive = "off" | "checking" | "ready" | "not-ready";

/** Exactly the backend's ready shape — anything else is not ready. */
export function isReadyBody(body: unknown): boolean {
  if (!body || typeof body !== "object") return false;
  const b = body as { api?: unknown; ready?: unknown };
  return b.api === "guided-path" && b.ready === true;
}

/** Ask the backend once. Resolves true ONLY on the ready shape; never rejects. */
export async function fetchGuidedReadiness(timeoutMs: number = READINESS_TIMEOUT_MS): Promise<boolean> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<boolean>((resolve) => {
    timer = setTimeout(() => resolve(false), timeoutMs);
  });
  const call = api.get<unknown>(READINESS_PATH).then(isReadyBody, () => false);
  try {
    return await Promise.race([call, timeout]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}

let readinessCache: { at: number; answer: Promise<boolean> } | null = null;

/**
 * THE decision: true only when the frontend flag is on AND the backend said ready.
 * Flag off → false without any network call (so a publish with the flag off behaves exactly
 * as before).
 */
export function guidedPathLive(timeoutMs?: number): Promise<boolean> {
  if (!guidedPathEnabled()) return Promise.resolve(false);
  const now = Date.now();
  if (!readinessCache || now - readinessCache.at > READINESS_CACHE_MS) {
    readinessCache = { at: now, answer: fetchGuidedReadiness(timeoutMs) };
  }
  return readinessCache.answer;
}

/** Tests only: forget the cached answer. */
export function resetGuidedReadinessCache(): void {
  readinessCache = null;
}
