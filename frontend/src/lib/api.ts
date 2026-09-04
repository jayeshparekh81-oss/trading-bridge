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
    throw new ApiError(0, "Network error — is the backend running?");
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
    throw new ApiError(401, "Session expired. Please login again.");
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
    const detailText =
      typeof d === "string" ? d : fromObject || data.message || `HTTP ${res.status}`;
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
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${BASE}${endpoint}`, { method: "GET", headers });
  } catch {
    throw new ApiError(0, "Network error — is the backend running?");
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
    throw new ApiError(401, "Session expired. Please login again.");
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail?.message || data.detail || `HTTP ${res.status}`, data);
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
