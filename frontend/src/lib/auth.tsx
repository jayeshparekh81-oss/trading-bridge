"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";
import { api, ApiError, setTokens, clearTokens } from "./api";
import { safeNextPath } from "@/lib/safe-next";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  phone: string | null;
  is_active: boolean;
  is_admin: boolean;
  /** RBAC role from migration 013/014 — one of ``user`` /
   * ``pro_user`` / ``creator`` / ``admin`` / ``super_admin``.
   * Optional for backwards compatibility with cached payloads
   * from before the migration. */
  role?: string;
  telegram_chat_id: string | null;
  notification_prefs: Record<string, boolean>;
  created_at: string;
  /** Onboarding state from migration 021. 0 = not started,
   * 1-5 = active step, 6 = complete. Optional for any pre-021
   * cached payload that may still be in transit. */
  onboarding_step?: number;
  onboarding_completed_at?: string | null;
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  /** `next` — where to land afterwards. Sanitised via safeNextPath (an
   *  attacker-supplied ?next= is an open redirect); defaults to "/". */
  login: (email: string, password: string, next?: string) => Promise<void>;
  register: (
    data: { email: string; password: string; full_name: string; phone?: string },
    next?: string,
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const fetchUser = useCallback(async () => {
    try {
      const u = await api.get<User>("/auth/me");
      setUser(u);
    } catch (err) {
      // Only a REAL rejection of the session (401 after the refresh attempt)
      // may log the customer out. A network blip — status 0 — or a 5xx from
      // a restarting backend must not: during a ~30s container recreate this
      // used to clear both tokens and bounce every customer to /login, and
      // the discarded refresh token meant they could not come back without
      // re-entering their password. On a transient failure we keep the
      // tokens; the next request (or reload) simply retries.
      const status = err instanceof ApiError ? err.status : -1;
      if (status === 401) {
        clearTokens();
        setUser(null);
      }
      // else: transient — keep tokens AND the last known user, so an
      // already-open session is not bounced to /login by a 30-second blip.
    }
  }, []);

  // Check auth on mount
  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("tb_access_token") : null;
    if (token) {
      fetchUser().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, [fetchUser]);

  const login = useCallback(
    async (email: string, password: string, next?: string) => {
      try {
        const tokens = await api.post<AuthTokens>("/auth/login", { email, password }, true);
        setTokens(tokens.access_token, tokens.refresh_token);
        await fetchUser();
        toast.success("Login successful!");
        // safeNextPath, not `next` — this push happens with a live session, so
        // an unchecked value here is an authenticated open redirect.
        router.push(safeNextPath(next));
      } catch (err) {
        const msg = err instanceof ApiError ? err.detail : "Login failed";
        toast.error(msg);
        throw err;
      }
    },
    [fetchUser, router],
  );

  const register = useCallback(
    async (
      data: { email: string; password: string; full_name: string; phone?: string },
      next?: string,
    ) => {
      try {
        await api.post("/auth/register", data, true);
        toast.success("Account created! Logging in...");
        // Auto-login after register
        const tokens = await api.post<AuthTokens>("/auth/login", { email: data.email, password: data.password }, true);
        setTokens(tokens.access_token, tokens.refresh_token);
        await fetchUser();
        router.push(safeNextPath(next));
      } catch (err) {
        const msg = err instanceof ApiError ? err.detail : "Registration failed";
        toast.error(msg);
        throw err;
      }
    },
    [fetchUser, router],
  );

  const logout = useCallback(() => {
    api.post("/auth/logout", {}).catch(() => {});
    clearTokens();
    setUser(null);
    toast.success("Logged out");
    router.push("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, isLoading, isAuthenticated: !!user, login, register, logout }),
    [user, isLoading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
