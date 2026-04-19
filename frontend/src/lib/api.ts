/**
 * API client — auto-attaches JWT, handles 401 refresh, typed responses.
 *
 * Usage:
 *   const trades = await api.get<TradeList>("/users/me/trades");
 *   const tokens = await api.post<AuthTokens>("/auth/login", { email, password });
 */

const BASE = process.env.NEXT_PUBLIC_API_URL ? `${process.env.NEXT_PUBLIC_API_URL}/api` : "/api";

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
    throw new ApiError(
      res.status,
      data.detail || data.message || `HTTP ${res.status}`,
      data,
    );
  }

  return data as T;
}

// ── Public API ─────────────────────────────────────────────────────────

export const api = {
  get: <T>(url: string) => request<T>(url, { method: "GET" }),
  post: <T>(url: string, body?: unknown, skipAuth = false) =>
    request<T>(url, { method: "POST", body: body ? JSON.stringify(body) : undefined }, skipAuth),
  put: <T>(url: string, body?: unknown) =>
    request<T>(url, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(url: string) => request<T>(url, { method: "DELETE" }),
};
