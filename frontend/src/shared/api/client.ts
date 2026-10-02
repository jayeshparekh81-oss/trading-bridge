/**
 * API client — auto-attaches JWT, handles 401 refresh, typed responses.
 *
 * Usage:
 *   const trades = await api.get<TradeList>("/users/me/trades");
 *   const tokens = await api.post<AuthTokens>("/auth/login", { email, password });
 */

// Hotfix 2026-05-17: hardcoded production fallback (see
// WS_URL_FIX_DIAGNOSIS.md). Env var still takes precedence when set.
// Previous fallback "/api" relied on the next.config rewrite, which
// worked for REST but masked the missing env var that broke WS + /health.
const BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api`
  : "https://api.tradetri.com/api";

const TOKEN_KEY = "tb_access_token";
const REFRESH_KEY = "tb_refresh_token";

// ── Helpers ────────────────────────────────────────────────────────────

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// ── Customer words for failures that carry none ────────────────────────

/** What the platform's security middleware leaves of ANY 5xx JSON body
 *  (backend/app/middleware/security.py:240 SensitiveDataFilterMiddleware). Found by the
 *  26 Sep guided-path walk: the live broker modal showed this raw text to a customer. */
export const SCRUBBED_5XX_DETAIL = "internal error";
/** What a customer reads instead: what it means + what to do, never a code — in the customer's
 *  language (2 Oct 2026: English by default). The `_HI` constants are the Hinglish lines by name. */
export const SERVER_TROUBLE_HI =
  "Hamari taraf abhi kuch gadbad hai — aapka kaam save hai. 1-2 minute baad dobara try karo.";
export const NETWORK_TROUBLE_HI =
  "Internet ya hamara server abhi jawab nahi de raha — connection dekho aur dobara try karo.";
export const REQUEST_FAILED_HI = "Yeh kaam abhi nahi ho paaya — dobara try karo.";
const SESSION_EXPIRED_HI = "Aapka login purana ho gaya — dobara login karo. Aapka kaam save hai.";
const EN = {
  server: "Something is wrong on our side right now — your work is saved. Try again in 1-2 minutes.",
  network: "The internet or our server is not answering right now — check your connection and try again.",
  failed: "This did not go through — try again.",
  session: "Your login has expired — log in again. Your work is saved.",
};
/** The customer's language, read from the same two keys the LanguageProvider writes (no import of the
 *  React layer from this module, on purpose). Server-side, or with no explicit choice: English. */
export function clientLang(): "en" | "hinglish" | "hi" | "gu" {
  try {
    if (typeof window === "undefined" || window.localStorage.getItem("tradetri_language_chosen") !== "1") return "en";
    const v = window.localStorage.getItem("tradetri_language");
    return v === "hinglish" || v === "hi" || v === "gu" || v === "en" ? v : "en";
  } catch {
    return "en";
  }
}
const inHinglish = () => clientLang() === "hinglish";
export const serverTroubleLine = () => (inHinglish() ? SERVER_TROUBLE_HI : EN.server);
export const networkTroubleLine = () => (inHinglish() ? NETWORK_TROUBLE_HI : EN.network);
export const requestFailedLine = () => (inHinglish() ? REQUEST_FAILED_HI : EN.failed);
const sessionExpiredLine = () => (inHinglish() ? SESSION_EXPIRED_HI : EN.session);
/** The header the backend reads to answer in the customer's language (the guided path's screen copy). */
export const LANG_HEADER = "X-Tradetri-Lang";

// ── Error class ────────────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;
  detail: string;
  data: unknown;

  constructor(status: number, detail: string, data?: unknown) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.data = data;
  }
}

// ── Core fetch ─────────────────────────────────────────────────────────

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;

  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  skipAuth = false,
  retried = false,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    [LANG_HEADER]: clientLang(),
    ...(options.headers as Record<string, string> | undefined),
  };

  if (!skipAuth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${BASE}${endpoint}`, { ...options, headers });
  } catch {
    throw new ApiError(0, networkTroubleLine());
  }

  // 401 → attempt token refresh once
  if (res.status === 401 && !retried && !skipAuth) {
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = refreshAccessToken().finally(() => {
        isRefreshing = false;
        refreshPromise = null;
      });
    }
    const ok = await (refreshPromise ?? Promise.resolve(false));
    if (ok) {
      return request<T>(endpoint, options, skipAuth, true);
    }
    // Refresh failed → clear and let caller handle
    clearTokens();
    throw new ApiError(401, sessionExpiredLine());
  }

  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    // ``detail`` may be a structured object (the 402 paywall body
    // {code, message, upgrade_url, limit, used}; webhook/backtest validation
    // bodies). ApiError.detail is typed string and callers render it directly
    // as a React child — an object there white-screens the builders. Flatten
    // to the human message here; the raw body stays on ``data`` for callers
    // that branch on ``data.detail.code``.
    const d: unknown = data.detail;
    const fromObject =
      d && typeof d === "object" && typeof (d as { message?: unknown }).message === "string"
        ? (d as { message: string }).message
        : null;
    // A scrubbed 5xx ("internal error") or a body with nothing in it is never shown raw:
    // the customer gets what it means and what to do (never a status code).
    const scrubbed = res.status >= 500 && (d === SCRUBBED_5XX_DETAIL || d === undefined || d === null);
    const detailText = scrubbed
      ? serverTroubleLine()
      : typeof d === "string" ? d : fromObject || data.message || requestFailedLine();
    throw new ApiError(res.status, detailText, data);
  }

  return data as T;
}

// ── Public API ─────────────────────────────────────────────────────────

/**
 * Authenticated file download.
 *
 * A plain `<a href>` cannot be used here: auth is a Bearer token in
 * localStorage, not a cookie, so a bare link would arrive at the API with no
 * credentials and 401. This fetches with the same token (and the same
 * one-shot refresh on 401) as `request()`, then hands the bytes to the
 * browser as a download. It never parses the body — `request()` always
 * `.json()`s, which is why it cannot be reused for a CSV.
 *
 * Returns the number of bytes handed to the browser, so a caller can tell
 * an empty file from a failed one.
 */
async function download(
  endpoint: string,
  filename: string,
  retried = false,
): Promise<number> {
  const headers: Record<string, string> = { [LANG_HEADER]: clientLang() };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${BASE}${endpoint}`, { method: "GET", headers });
  } catch {
    throw new ApiError(0, networkTroubleLine());
  }

  if (res.status === 401 && !retried) {
    if (!isRefreshing) {
      isRefreshing = true;
      refreshPromise = refreshAccessToken().finally(() => {
        isRefreshing = false;
        refreshPromise = null;
      });
    }
    const ok = await (refreshPromise ?? Promise.resolve(false));
    if (ok) return download(endpoint, filename, true);
    clearTokens();
    throw new ApiError(401, sessionExpiredLine());
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const d = data.detail;
    const scrubbed = res.status >= 500 && (d === SCRUBBED_5XX_DETAIL || d === undefined || d === null);
    throw new ApiError(res.status, scrubbed ? serverTroubleLine() : d?.message || d || requestFailedLine(), data);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    // Give the click a tick to start before the URL goes away.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return blob.size;
}

export const api = {
  get: <T>(url: string) => request<T>(url, { method: "GET" }),
  download,
  post: <T>(url: string, body?: unknown, skipAuth = false) =>
    request<T>(url, { method: "POST", body: body ? JSON.stringify(body) : undefined }, skipAuth),
  put: <T>(url: string, body?: unknown) =>
    request<T>(url, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(url: string, body?: unknown) =>
    request<T>(url, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(url: string) => request<T>(url, { method: "DELETE" }),
};
